# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a finished agent run is allowed to leave behind.

Two of these decline a run's outcome and one publishes it, but all three live
in the same window -- after the spawn returns, before the handler's
`gh.write_pinned_state` -- and they share one rule: the handler owns that
write. `_ignore_if_interrupted` and `_paused_during_agent_run` say "not this
run" by returning True and letting the caller `return` without writing, so the
in-memory `PinnedState` mutations it already staged are dropped and the next
tick re-derives the run from the state the prior tick left. `_park_awaiting_human`
goes the other way -- it posts the HITL comment, sets `awaiting_human`, and
ratchets `last_action_comment_id` past it -- and still leaves the write to the
caller, so a park composes with whatever else that handler staged rather than
committing ahead of it.

The two refusals answer different questions and neither covers the other.
Interruption is read off the result the shutdown sweep produced. A mid-run
`paused` / `backlog` is visible only on a FRESHLY fetched issue: the dispatcher
screened the hard-skip labels once at tick start, and the handler has been
holding that snapshot for however long the agent ran.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator.agents import AgentResult
from orchestrator.github.client import GitHubClient
from orchestrator.github.labels import hard_skip_control_label
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.state import stage_name

log = logging.getLogger("orchestrator.workflow")


def _ignore_if_interrupted(issue: Issue, agent_result: AgentResult) -> bool:
    """True when `agent_result` came from a run the shutdown sweep killed
    mid-flight (SIGTERM/SIGKILL -- `AgentResult.interrupted`).

    Such a run carries no trustworthy outcome: `last_message` is empty or a
    partial transcript chunk and no commit / question / timeout signal can be
    read from it. Dev-resume stage handlers call this BEFORE their
    timeout/question/dirty/push branches and `return` WITHOUT writing pinned
    state on a True result, so durable GitHub state stays exactly as the prior
    tick left it and the next orchestrator process re-runs the resume from
    scratch. Returning quietly here is what keeps the interrupted path from
    posting an agent-question HITL comment, consuming an `awaiting_human`
    park, advancing an action/comment watermark, or interpreting partial
    `last_message` content -- all of which the in-memory `state` mutations the
    caller already made would persist on a normal `write_pinned_state`.

    Logs once at INFO so the interruption is visible without being mistaken
    for a real silence/timeout park.
    """
    if not agent_result.interrupted:
        return False
    log.info(
        "issue=#%d agent run interrupted by shutdown sweep; leaving durable "
        "state untouched for retry by the next process",
        issue.number,
    )
    return True


def _paused_during_agent_run(gh: GitHubClient, issue: Issue) -> bool:
    """True when a hard-skip control label (`paused` / `backlog`) was applied
    to `issue` while an agent run was in flight.

    The dispatcher and `_process_issue` read the issue's labels once, at tick
    start, and skip a hard-skipped issue before any handler runs. But a stage
    that spawns an agent holds that label snapshot for the whole run -- minutes,
    typically -- so an operator who applies `paused` mid-run would otherwise not
    take effect until the run's results were already published: PR opened, label
    flipped, HITL park posted, action watermark consumed, pinned state advanced.

    Stage handlers call this right after an agent run returns, BEFORE any of
    that disposition, and `return` WITHOUT writing pinned state on a True result
    -- mirroring `_ignore_if_interrupted`. Durable GitHub state is left exactly
    as the prior tick had it and the agent's committed work stays on the branch,
    so once the operator removes the label the next tick republishes it through
    the normal recovered-worktree path.

    The label is read from a FRESHLY fetched issue (`gh.get_issue`), never the
    stale handler `issue` whose labels were snapshotted before the run -- the
    whole point is to catch a label applied mid-run. A fetch failure returns
    False (publish as before): the guard is an additive safety net and must not
    itself strand a run that would otherwise have completed.
    """
    try:
        fresh = gh.get_issue(issue.number)
    except Exception:  # noqa: BLE001 - the guard is additive and must not strand a finished run
        log.debug(
            "issue=#%d not retrievable for post-agent pause check; proceeding",
            issue.number,
        )
        return False
    skip_label = hard_skip_control_label(fresh)
    if skip_label is None:
        return False
    log.info(
        "issue=#%d acquired %r during the agent run; leaving durable state "
        "untouched until the label is removed",
        issue.number, skip_label,
    )
    return True


def _park_awaiting_human(
    gh: GitHubClient, issue: Issue, state: PinnedState, message: str,
    *,
    reason: str | None = None,
) -> None:
    """Post `message` and mark the issue as awaiting a human reply.

    Caller is responsible for `gh.write_pinned_state` afterwards (mirrors the
    existing _on_question / _on_dirty_worktree contract). Clears any stale
    `park_reason` -- a transient park (e.g. in_review `unmergeable`)
    followed by a follow-up question/timeout park would otherwise leave
    the transient reason behind. Callers that re-park for a transient
    reason re-set `park_reason` immediately after this call.

    `reason` is recorded only in the emitted `park_awaiting_human` audit
    event; the durable `park_reason` field in pinned state is still cleared
    here (callers that need a transient reason re-set it themselves -- see
    above), so passing a reason does not change observable behavior.
    """
    _comments._post_issue_comment(gh, issue, state, message)
    state.set("awaiting_human", True)
    state.set("park_reason", None)
    latest = gh.latest_comment_id(issue)
    if latest is not None:
        state.set("last_action_comment_id", latest)
    # Read the label AFTER the comment post and state writes so the
    # captured stage reflects the handler that drove the park (the label
    # itself is unchanged by this call -- callers relabel only after the
    # `write_pinned_state` they do next).
    gh.emit_event(
        "park_awaiting_human",
        issue_number=issue.number,
        stage=stage_name(gh.workflow_label(issue)),
        reason=reason,
    )
