# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Why a run that produced no publishable commit stopped, and what that costs.

A commit-less run reaches exactly one of three parks, and the difference
between them is not cosmetic: `park_reason` is the field
`/orchestrator continue` keys off. A quota notice and an empty result are both
tagged `agent_silent` -- retryable session failures an operator can continue
after the reset -- and both advance the silent-park streak that eventually
rotates a poisoned session to a fresh spawn. A real question is the opposite:
it clears the reason and zeroes the streak, because it needs a human's words
before anything should run again, and a stale transient reason left behind
would let a later tick auto-recover over a question nobody answered.

The dirty-worktree park is the fourth, and it exists to refuse a push rather
than to explain a failure: the branch would omit the uncommitted files, so the
PR would not match what the agent produced. Every park here posts the HITL
comment, ratchets `last_action_comment_id` past it so the next tick reads the
human's reply and not its own notice, and emits `park_awaiting_human` -- but
leaves the pinned-state write to the handler, so the park composes with
whatever else that tick staged.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments, messages as _messages
from orchestrator.workflow.stages.implementing import (
    session_read as _session_read,
    state as _state,
)

log = logging.getLogger("orchestrator.workflow")


def _mark_agent_silent_park(state: PinnedState) -> None:
    """Flag a retryable `agent_silent` park and advance the silent-park streak.

    Shared by the session-limit and empty-output parks: both are retryable
    `agent_silent` failures, not real questions. `_resume_dev_with_text` reads
    the streak (via `_dev_session_retirement_reason`) to rotate a poisoned
    session to a fresh spawn once it reaches `_SILENT_PARKS_BEFORE_FRESH_SESSION`.
    """
    count = int(state.get(_state._SILENT_PARK_COUNT) or 0)
    state.set(_state._AWAITING_HUMAN, True)
    state.set(_state._PARK_REASON, "agent_silent")
    state.set(_state._SILENT_PARK_COUNT, count + 1)


def _park_session_limit(
    gh: GitHubClient, issue: Issue, state: PinnedState, raw: str
) -> str:
    """Park a session/usage-quota notice as a RETRYABLE session failure.

    A known quota notice ("You've hit your session limit ...") is non-empty but
    is NOT a real agent question: the session is healthy, the account quota is
    exhausted, and the only recovery is to wait for the reset and retry.
    Parking it as `agent_silent` (the same reason a silent poisoned resume
    uses) lets an operator's `/orchestrator continue` after the reset drop the
    session and re-ground a fresh one; classifying it as a real question
    (`park_reason=None`) would refuse that continue as "needs your actual
    guidance". The silent-park streak is incremented so a session that keeps
    returning the quota notice is eventually rotated, mirroring the
    empty-message branch. Returns the distinct EVENT reason
    (`agent_session_limit`) for observability -- the pinned `park_reason` stays
    `agent_silent` (the control field `/orchestrator continue` keys off).
    """
    quoted = _session_read._as_blockquote(raw)
    _comments._post_issue_comment(
        gh, issue, state,
        f"{config.HITL_MENTIONS} agent hit a session/usage limit and "
        "stopped; retry with `/orchestrator continue` once it "
        f"resets:\n\n{quoted}",
    )
    _mark_agent_silent_park(state)
    return "agent_session_limit"


def _park_real_question(
    gh: GitHubClient, issue: Issue, state: PinnedState, raw: str
) -> str:
    """Park a genuine agent clarification question awaiting a human reply."""
    quoted = _session_read._as_blockquote(raw)
    _comments._post_issue_comment(
        gh, issue, state,
        f"{config.HITL_MENTIONS} agent needs your input to proceed:\n\n{quoted}",
    )
    state.set(_state._AWAITING_HUMAN, True)
    # Real question parks are not transient: they need a human reply before the
    # in_review ready-ping gates should run again. Clear any stale
    # `park_reason` left behind by a prior in_review unmergeable park, and reset
    # the silent-park streak.
    state.set(_state._PARK_REASON, None)
    state.set(_state._SILENT_PARK_COUNT, 0)
    return "agent_question"


def _park_silent_failure(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    agent_result: AgentResult,
) -> str:
    """Park a run that produced no commit AND no message as a silent failure.

    Callers only invoke `_on_question` when the worktree has no new commits, so
    an empty `last_message` is a silent failure, not a content question -- most
    often a poisoned resume of a session killed mid-stream (e.g. by a Claude
    rate limit). Tag the park `agent_silent` so `_resume_dev_with_text` can
    drop the dev session id after enough consecutive silent parks, and surface
    the situation accurately instead of impersonating a real question park.
    """
    diag = _messages._format_stderr_diagnostics(agent_result, "Agent")
    _comments._post_issue_comment(
        gh, issue, state,
        f"{config.HITL_MENTIONS} agent produced no output (likely a "
        f"session-resume failure); manual intervention needed.{diag}",
    )
    log.warning(
        "issue=#%s agent produced no output; exit_code=%d "
        "timed_out=%s stderr_tail=%r",
        issue.number, agent_result.exit_code, agent_result.timed_out,
        _messages._stderr_log_tail(agent_result),
    )
    _mark_agent_silent_park(state)
    return "agent_silent"


def _on_question(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    agent_result: AgentResult,
) -> None:
    raw = agent_result.last_message.strip()
    if raw and _session_read._is_session_limit_message(agent_result):
        park_reason = _park_session_limit(gh, issue, state, raw)
    elif raw:
        park_reason = _park_real_question(gh, issue, state, raw)
    else:
        park_reason = _park_silent_failure(gh, issue, state, agent_result)
    latest = gh.latest_comment_id(issue)
    if latest is not None:
        state.set(_state._LAST_ACTION_COMMENT_ID, latest)
    gh.emit_event(
        "park_awaiting_human",
        issue_number=issue.number,
        stage=gh.workflow_label(issue),
        reason=park_reason,
    )


def _on_dirty_worktree(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    agent_result: AgentResult,
    dirty: list[str],
) -> None:
    """Park instead of pushing when the agent left uncommitted changes.

    Pushing here would publish a branch that omits the dirty files, so the PR
    would not match what the agent actually produced. We surface the situation
    to the human and resume the codex session on their reply, identical to the
    question path.
    """
    _comments._post_issue_comment(
        gh, issue, state, _dirty_worktree_message(agent_result, dirty),
    )
    state.set(_state._AWAITING_HUMAN, True)
    # Mirror `_on_question`: this needs human input, so stale transient state
    # must not auto-recover over it.
    state.set(_state._PARK_REASON, None)
    state.set(_state._SILENT_PARK_COUNT, 0)
    latest = gh.latest_comment_id(issue)
    if latest is not None:
        state.set(_state._LAST_ACTION_COMMENT_ID, latest)
    gh.emit_event(
        "park_awaiting_human",
        issue_number=issue.number,
        stage=gh.workflow_label(issue),
        reason="dirty_worktree",
        dirty_files=len(dirty),
    )


def _dirty_worktree_message(
    agent_result: AgentResult, dirty: list[str],
) -> str:
    shown = dirty[:10]
    files_md = "\n".join(f"- `{file_path}`" for file_path in shown)
    if len(dirty) > len(shown):
        elided = len(dirty) - len(shown)
        files_md = f"{files_md}\n- … ({elided} more)"
    last_msg = agent_result.last_message.strip()
    tail = ""
    if last_msg:
        tail = f"\n\n_Last agent message:_\n\n{_session_read._as_blockquote(last_msg)}"
    return (
        f"{config.HITL_MENTIONS} agent committed but left {len(dirty)} "
        f"uncommitted change(s); refusing to push an incomplete branch. "
        f"Reply with guidance and the orchestrator will resume the session.\n\n"
        f"{files_md}{tail}"
    )
