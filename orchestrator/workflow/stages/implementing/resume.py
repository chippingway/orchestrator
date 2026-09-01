# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two ways a dev session is handed new text, and the call shape they keep.

`_resume_dev_with_text` is the resume every stage that owns a dev session goes
through -- implementing, validating, documenting, in_review, fixing, and
resolving_conflict -- so its signature is a contract several callers already
wrote against: positional `state` and `followup_text`, an optional `stage`
override, and keyword options. It is bound through an explicit `inspect`
signature rather than named parameters so that shape is enforced in one place
and a mistyped option raises instead of being ignored.

`_resume_developer_on_human_reply` is the narrower one: it reads the new
issue-level comments itself and is what implementing and validating park
against. Two rules matter more than the read. Untrusted authors are dropped
BEFORE anything else, so nothing an outsider posts on a parked issue reaches
the dev prompt or advances the consumed watermark. And the watermark is
advanced BEFORE the agent runs, because the dev DID see those comments in its
prompt: leaving it behind would let the validating -> in_review handoff replay
the same human reply as fresh PR feedback and resume the dev on input it
already handled, and advancing it afterwards would lose that record whenever
the run crashed.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Tuple

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.github.client import GitHubClient
from orchestrator.github.comments import filter_trusted
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments, prompts as _prompts
from orchestrator.workflow.stages.implementing import (
    execution as _execution,
    models as _models,
    state as _state,
)

_DEV_RESUME_SIGNATURE = inspect.Signature((
    inspect.Parameter("gh", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("spec", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("issue", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("resume_args", inspect.Parameter.VAR_POSITIONAL),
    inspect.Parameter(
        "stage",
        inspect.Parameter.KEYWORD_ONLY,
        default=None,
    ),
    inspect.Parameter("option_fields", inspect.Parameter.VAR_KEYWORD),
))


def _resume_dev_with_text(
    *args: Any,
    **kwargs: Any,
) -> Tuple[Path, AgentResult, bool]:
    """Resume the dev's locked-backend session with the given prompt text.

    `stage` overrides the recorded stage for every audit / analytics /
    trajectory record this run emits. It defaults to the label read off
    `issue`, which is correct whenever the caller fetched the issue fresh this
    tick. The CHANGES_REQUESTED fix path must pass it explicitly (`fixing`):
    it relabels validating -> fixing and then resumes on the SAME `Issue`
    object, whose cached `labels` PyGithub does not refresh after
    `set_labels`, so the label read would still report `validating` and
    attribute the developer run to the reviewer's stage.

    The backend is locked to whatever wrote `dev_session_id` (or the legacy
    `codex_session_id`) for this issue -- resuming across backends would need
    an inter-backend session bridge that does not exist. Clears the
    `awaiting_human` flag because the caller is reacting to a fresh human
    signal (issue or PR comment) by spawning the agent.

    After `_SILENT_PARKS_BEFORE_FRESH_SESSION` consecutive `agent_silent`
    parks on the current `dev_session_id`, the resume drops the session id
    and starts a fresh spawn instead. Sessions killed mid-stream (e.g. by a
    Claude rate limit) consistently return empty results on every subsequent
    resume; without this fallback every human "retry" comment burns another
    fresh-spawn retry slot on the same poisoned session.

    Proactive rotation: each resume increments a per-session `dev_resume_count`
    and, once it reaches `config.DEV_SESSION_MAX_RESUMES` (when that knob is
    > 0), the session is retired and the spawn goes fresh. `--resume` replays
    the entire accumulated transcript every time, so a session resumed many
    times creeps toward the model context window; rotating proactively rebuilds
    a small prompt from durable state (issue body + recent comments + the
    committed branch) and caps that creep before it overflows. Every fresh
    spawn -- whether triggered by rotation, the silent-park fallback, or
    poisoned-session recovery -- is prefixed with a re-grounding preamble
    (`_build_fresh_respawn_preamble`) because the prior session's in-memory
    reasoning is gone and only its committed work survives on the branch.

    A Claude resume that comes back with `No conversation found with session
    ID` (or a sibling marker), or with a `Prompt is too long` context-window
    overflow, is treated as the same poisoned-session condition but
    recognized immediately: the pinned session id is cleared and the call is
    retried once as a fresh spawn in the same worktree, so a Claude session
    whose transcript was GC'd or grew past the context window doesn't park
    (`agent_silent` for two ticks, or `awaiting_human` forever) before
    recovering.

    Returns `(worktree, result, paused)`. `paused` is the live-pause decision
    -- True only when `pause_guard` is set AND a hard-skip control label
    (`paused` / `backlog`) was applied to a freshly fetched issue while an agent
    run was in flight. `pause_guard` is opt-in (default False): every
    developer-resume caller -- implementing, validating, documenting, in_review,
    fixing, and resolving_conflict -- passes it True and honors the flag. The
    check runs after BOTH agent runs -- the initial resume/spawn AND the
    poisoned-session fresh retry -- because each has its own live-pause window:
    the first fires before the retry spawns a second agent, and the second
    before the retry's result is persisted. When it fires the helper stops
    before the session id is persisted and before `awaiting_human` is cleared,
    and the caller must honor the returned flag by stopping too -- the decision
    is propagated, not re-fetched, so there is no window where the caller reads
    the label differently than the helper did.
    """
    bound_fields = _DEV_RESUME_SIGNATURE.bind(*args, **kwargs)
    bound_fields.apply_defaults()
    request = _models._DevResumeRequest(
        gh=bound_fields.arguments["gh"],
        spec=bound_fields.arguments["spec"],
        issue=bound_fields.arguments["issue"],
        resume_args=bound_fields.arguments["resume_args"],
        option_fields=bound_fields.arguments["option_fields"],
        stage=bound_fields.arguments["stage"],
    )
    return _execution._DevResumeContext.build(request).execute()


_resume_dev_with_text.__signature__ = _DEV_RESUME_SIGNATURE


def _resume_developer_on_human_reply(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
    *,
    pause_guard: bool = False,
) -> Tuple[Path, AgentResult, bool] | None:
    """Resume the developer's agent session with new issue-level comments.

    Returns (worktree, agent_result, paused) on resume, or None if there are no
    new comments since the last park (caller should return without writing
    state). `paused` is forwarded from `_resume_dev_with_text` and is only ever
    True when `pause_guard` is set; both callers (implementing and validating)
    pass it True and honor the flag.

    Used by `implementing` and `validating` -- both deliberately watch only
    the issue's comment thread, not the PR's. The `in_review` handler watches
    PR comments too via `_resume_dev_with_text` directly.

    Bumps `last_action_comment_id` to the highest consumed comment id BEFORE
    spawning the agent. Without this, a successful resume during implementing
    or validating leaves `last_action_comment_id` at the prior park id, so
    the validating->in_review handoff treats the just-consumed human reply
    as fresh PR feedback and re-resumes the dev on input it has already
    handled. This pre-resume bump is also robust to mid-resume failures:
    if the agent crashes or times out, those comments are still recorded
    as consumed (the dev DID see them via the resume prompt), and the
    failure is surfaced via the timeout/dirty/question paths instead.

    Untrusted authors are dropped up front so nothing they post drives the
    resume: with `ALLOWED_ISSUE_AUTHORS` set an outsider reply posted while the
    issue is parked awaiting human must not reach the dev prompt NOR advance the
    consumed watermark. Only trusted comments are consumed, so an outsider reply
    trailing a trusted one is left unconsumed rather than persisted as the
    watermark; an all-untrusted batch is treated as "no new reply".
    """
    last_action_id = state.get(_state._LAST_ACTION_COMMENT_ID)
    new_comments = filter_trusted(gh.comments_after(issue, last_action_id))
    if not new_comments:
        return None
    consumed_max = max(comment.id for comment in new_comments)
    state.set(_state._LAST_ACTION_COMMENT_ID, consumed_max)

    followup = "\n\n".join(
        _comments._quote_comment_line(comment)
        for comment in new_comments if comment.body
    )
    followup = f"{followup}\n\n{_prompts._FOREGROUND_ONLY_NOTE}"
    return _resume_dev_with_text(
        gh, spec, issue, state, followup, pause_guard=pause_guard,
    )
