# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The decomposer session an issue is locked to: taken, resumed, and retired.

A resume has to land on the backend that opened the session -- there is no
bridge between a codex session id and a claude one -- so the agent spec is
pinned on the issue at the first spawn, before the spawn can fail, and read
back from there on every later tick whatever the current `DECOMPOSE_AGENT`
says. That lock is what makes an env flip safe to do while issues are in
flight, and writing it early is what keeps a backend that returned no session
id from leaving the issue unattributed.

Two things end a session. A human reply resumes it with the new comments
quoted. A user-content edit retires it: the manifest tracking it produced is
wiped so recovery cannot mistake the reroute for a crash, the session id is
dropped so the next tick starts a fresh conversation against the new body --
and only the session id, because the locked spec must outlive the reset for
the same reason it exists. Children the wiped manifest tracked stay open on
GitHub and are named as orphans in the notice; which of them still apply to
the edited body is the operator's call, not ours.
"""
from __future__ import annotations

from typing import Optional, Tuple

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.git.worktrees import decomposition as _worktree_decomposition
from orchestrator.github.client import GitHubClient
from orchestrator.github.comments import filter_trusted
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.engine import drift as _drift
from orchestrator.workflow.engine import prompts as _prompts
from orchestrator.workflow.engine import usage as _usage
from orchestrator.workflow.stages.decomposition import state as _state
from orchestrator.workflow.stages.decomposition.models import _DecomposerSession
from orchestrator.workflow.stages.implementing import session as _dev_session


def _read_decomposer_session(
    state: PinnedState,
) -> Tuple[str, str, tuple[str, ...], Optional[str]]:
    """Return (spec, backend, extra_args, decomposer_session_id) for an issue.

    Mirrors `_read_dev_session`: `spec` is the full configured agent
    command string the next run will use, returned so callers can
    persist it verbatim BEFORE invoking `run_agent` -- a fresh
    decomposer that produces a manifest without surfacing a session id
    (a backend hiccup in the JSONL output, an empty `-o` file) would
    otherwise leave `decomposer_agent` unset and a later
    `DECOMPOSE_AGENT` env flip could retarget the awaiting-human
    resume at a backend that never ran on this issue.

    Legacy bare-backend values (`"codex"` / `"claude"`) re-parse to
    `(backend, ())` and round-trip cleanly. When the issue has never
    been spawned, returns the current config's
    `(DECOMPOSE_AGENT_SPEC, DECOMPOSE_AGENT, DECOMPOSE_AGENT_ARGS, None)`.
    """
    stored = state.get("decomposer_agent")
    if stored:
        spec = str(stored)
        backend, args = config._parse_agent_spec("decomposer_agent", spec)
        sid = state.get("decomposer_session_id")
        return spec, backend, args, None if sid is None else str(sid)
    return (
        config.DECOMPOSE_AGENT_SPEC,
        config.DECOMPOSE_AGENT,
        config.DECOMPOSE_AGENT_ARGS,
        None,
    )


def _spawn_fresh_decomposer(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> Optional[AgentResult]:
    """Consume a retry slot and spawn a fresh decomposer session.

    Returns the agent result, or None when the retry budget is exhausted
    (the budget helper already wrote the park; caller must return).
    """
    if not _dev_session._check_and_increment_retry_budget(
        gh, issue, state, stage="decomposing"
    ):
        gh.write_pinned_state(issue, state)
        return None
    wt = _worktree_decomposition._ensure_decompose_worktree(spec, issue.number)
    session = _DecomposerSession(*_read_decomposer_session(state))
    # Persist the spec BEFORE the spawn so a backend hiccup
    # that yields no `session_id` -- yet still produces a
    # manifest in the worktree or parks awaiting human -- does
    # not leave `decomposer_agent` unset. A later
    # `DECOMPOSE_AGENT` flip would otherwise retarget the next
    # awaiting-human resume at a backend that never ran on
    # this issue. Storing the parsed backend alone would also
    # strip configured CLI args on subsequent resumes.
    state.set("decomposer_agent", session.spec)
    decomposer_result = _usage._run_agent_tracked(
        gh, issue.number,
        agent_role="decomposer",
        stage="decomposing",
        backend=session.backend,
        prompt=_prompts._build_decompose_prompt(
            spec, issue, _comments._recent_comments_text(issue),
            config.default_repo_specs(),
        ),
        cwd=wt,
        agent_spec=session.spec,
        extra_args=session.extra_args,
        retry_count=state.get("retry_count"),
    )
    if decomposer_result.session_id:
        state.set("decomposer_session_id", decomposer_result.session_id)
    return decomposer_result


def _decomposer_followup(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> Optional[str]:
    comments = filter_trusted(
        gh.comments_after(issue, state.get(_state._LAST_ACTION_COMMENT_ID))
    )
    if not comments:
        return None
    state.set(
        _state._LAST_ACTION_COMMENT_ID,
        max(comment.id for comment in comments),
    )
    return "\n\n".join(
        _comments._quote_comment_line(comment)
        for comment in comments if comment.body
    )


def _resume_decomposer_on_human_reply(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> Optional[AgentResult]:
    """Resume the decomposer's locked-backend session with new comments.

    Returns the agent result, or None if there are no new comments since
    the last park (caller should return without writing state).

    Mirrors `_resume_developer_on_human_reply` but on the decomposer
    session. The backend is locked to whichever wrote
    `decomposer_session_id`; resuming across backends would need an
    inter-backend session bridge that does not exist.
    """
    followup = _decomposer_followup(gh, issue, state)
    if followup is None:
        return None
    wt = _worktree_decomposition._decompose_worktree_path(spec, issue.number)
    if not wt.exists():
        wt = _worktree_decomposition._ensure_decompose_worktree(
            spec, issue.number,
        )
    session = _DecomposerSession(*_read_decomposer_session(state))
    decomposer_result = _usage._run_agent_tracked(
        gh, issue.number,
        agent_role="decomposer",
        stage="decomposing",
        backend=session.backend,
        prompt=followup,
        cwd=wt,
        agent_spec=session.spec,
        resume_session_id=session.session_id,
        extra_args=session.extra_args,
        retry_count=state.get("retry_count"),
    )
    state.set(_state._AWAITING_HUMAN, False)
    return decomposer_result


def _decomposition_drift_notice(orphans: list) -> str:
    notice = (
        ":pencil2: issue content changed; re-running decomposer against "
        "the updated body."
    )
    if not orphans:
        return notice
    orphan_list = _state._issue_ref_list(orphans)
    return (
        f"{notice} The previously-tracked children ({orphan_list}) will be "
        "ORPHANED -- the orchestrator no longer tracks them; please close "
        "any that no longer apply to the updated requirements."
    )


def _clear_decomposition_manifest(state: PinnedState) -> None:
    state.set("decomposer_session_id", None)
    state.set(_state._CHILDREN, [])
    state.set("dep_graph", {})
    state.set("expected_children_count", None)
    state.set(_state._UMBRELLA, None)
    state.set(_state._AWAITING_HUMAN, False)
    state.set(_state._PARK_REASON, None)


def _reset_decomposing_on_drift(
    gh: GitHubClient, issue: Issue, state: PinnedState
) -> None:
    """Wipe manifest tracking and the decomposer session when the issue
    body drifted, so the fresh-spawn path re-derives a manifest against
    the updated body THIS tick.

    Runs at the very top of `_handle_decomposing` -- the spec requires
    "at the start of every per-tick handler". Ordering it before the
    half-finished recovery is what stops the recovery branch from
    finalizing to `blocked` / `umbrella` against a stale manifest when the
    human edited the issue body during a crash window. When drift IS
    detected we clear the manifest tracking (children, dep_graph,
    expected_children_count, umbrella) so the recovery branch is bypassed
    and the fresh-spawn path derives a new manifest. Previously-created
    children are listed as orphans in the notice -- they remain on GitHub
    but the orchestrator no longer tracks them.

    Unlike the pre-implementation handlers (which call
    `_route_drift_to_decomposing` and RETURN), this issue is already
    `decomposing`, so we mutate state in place and fall through -- the
    caller keeps running and spawns the decomposer this tick.
    """
    new_hash = _drift._detect_user_content_change(gh, issue, state)
    if new_hash is None:
        return
    _comments._post_issue_comment(
        gh, issue, state,
        _decomposition_drift_notice(list(state.get(_state._CHILDREN) or [])),
    )
    state.set("user_content_hash", new_hash)
    # Drop only the SESSION id -- preserve `decomposer_agent`
    # (the locked role spec). Lock-on-first-spawn means a
    # mid-flight `DECOMPOSE_AGENT` env flip must not retarget
    # an in-flight issue at a different backend; the fresh
    # spawn below picks up the recorded spec via
    # `_read_decomposer_session`.
    _clear_decomposition_manifest(state)
