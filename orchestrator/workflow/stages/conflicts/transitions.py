# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two shapes every state-changing exit of this stage shares.

A park is never just a comment: `_park_awaiting_human` mutates the in-memory
pinned state, so the `write_pinned_state` that persists it has to follow on the
same tick or the HITL flag is lost and the next tick re-runs the rebase. This
stage has eleven park sites, which is exactly why the pair lives on one owner
rather than being repeated at each.

A pushed round is the same argument at a larger size: reset `review_round`
because rebasing rewrote the SHAs the reviewer approved, bump `conflict_round`
so the cap can still fire, stamp when it resolved, emit the audit event, flip
the label, and write once. Five exits earn that tail -- the recovered push, the
clean base rebase, the agent resolution, the drift resume, and the no-op flip
(which shares only the counter half, having resolved nothing) -- and the audit
event's `outcome` is what lets a tail of the JSONL sink tell them apart without
re-reading the code.
"""
from __future__ import annotations

import logging
from typing import Optional

from orchestrator.git.measurement import commits as _measurement_commits
from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.late_split import (
    formats as _formats,
    payloads as _payloads,
)
from orchestrator.workflow.engine import usage as _usage
from orchestrator.workflow.stages.conflicts import models as _models
from orchestrator.workflow.stages.conflicts import state as _state
from orchestrator.workflow.stages.implementing import (
    late_records as _late_records,
)
from orchestrator.workflow.state import WorkflowLabel

log = logging.getLogger("orchestrator.workflow")


# The revision a checkout's own head is named by.
_HEAD = "HEAD"


def _park_conflict(
    ctx: _models._ConflictContext, message: str, *, reason: str,
) -> None:
    """Park awaiting human and persist pinned state.

    Every `resolving_conflict` park pairs `_park_awaiting_human` with the
    matching `write_pinned_state`; routing them through here keeps the two
    from drifting apart across the handler's many exits.
    """
    _guards._park_awaiting_human(ctx.gh, ctx.issue, ctx.state, message, reason=reason)
    ctx.gh.write_pinned_state(ctx.issue, ctx.state)


def _emit_conflict_round_incremented(
    ctx: _models._ConflictContext,
    *,
    pr_number: int,
    new_round: int,
    outcome: str,
    sha: Optional[str] = None,
) -> None:
    """Record a `conflict_round` audit event when the counter ticks.

    Centralizes the bookkeeping so every increment site -- ahead-of-remote
    push recovery, up-to-date no-op flip, clean base-rebase push, agent-
    resolved conflict push, drift-pushed bounce -- emits the same shape.
    `outcome` distinguishes the increment cause so a tail of the JSONL sink
    can attribute rounds without re-reading the surrounding code.
    """
    ctx.gh.emit_event(
        _state._CONFLICT_ROUND,
        issue_number=ctx.issue.number,
        stage="resolving_conflict",
        pr_number=int(pr_number),
        sha=sha or None,
        action="incremented",
        conflict_round=int(new_round),
        outcome=outcome,
        review_round=int(ctx.state.get(_state._REVIEW_ROUND) or 0),
        retry_count=ctx.state.get("retry_count"),
    )


def _hand_resolved_round_to_validating(
    ctx: _models._ConflictContext,
    conflict_round: int,
    pr_number,
    *,
    outcome: str,
    sha: Optional[str],
) -> None:
    """Record a pushed conflict-resolution round and hand back to `validating`.

    Resets `review_round` (rebasing rewrites SHAs, so validation must
    re-approve the rebased branch), bumps `conflict_round`, stamps
    `last_conflict_resolved_at`, emits the `conflict_round` audit event, flips
    the label, and persists pinned state. Shared by every pushed-diff exit --
    recovered push, clean base rebase, agent resolution, and the drift resume.
    Docs do not run here: the single docs pass is deferred to the post-approval
    handoff to `documenting` in `_handle_validating`.
    """
    ctx.state.set(_state._REVIEW_ROUND, 0)
    ctx.state.set(_state._CONFLICT_ROUND, conflict_round + 1)
    ctx.state.set("last_conflict_resolved_at", _usage._now_iso())
    _forget_settled_round(ctx)
    _emit_conflict_round_incremented(
        ctx,
        pr_number=int(pr_number),
        new_round=conflict_round + 1,
        outcome=outcome,
        sha=sha,
    )
    ctx.gh.set_workflow_label(ctx.issue, WorkflowLabel.VALIDATING)
    ctx.gh.write_pinned_state(ctx.issue, ctx.state)


def _settles_the_held_round(outcome: str, sha: Optional[str]):
    """The round a hold owes this stage, named for the gate to write it down.

    A hold ends the tick: the resolution is committed, the issue is on
    `workflow:decomposing`, and the tail above never runs. But the round IS
    resolved -- a settled `single` verdict publishes the accepted commit from
    the adjudication -- and the resumed tick could not work out which of the
    two resolutions it was: the branch it comes back to already carries its
    base, which is the no-op flip's own reading and the one exit that resolves
    nothing and stamps no `last_conflict_resolved_at`.

    So the pair is handed to the gate and written inside its routed write,
    ahead of the relabel, and the resumed tick finishes the ORIGINAL outcome
    from it rather than re-deriving a wrong one.
    """
    return _late_records._Spends(fields=(
        (_state._SETTLED_OUTCOME, outcome),
        (_state._SETTLED_SHA, sha or ""),
    ))


def _finished_settled_round(
    ctx: _models._ConflictContext,
    sync: _models._WorktreeSync,
    conflict_round: int,
    pr_number,
) -> bool:
    """Finish a resolution the size gate held and an adjudication published.

    The receipt is the whole of what this tick knows about a round it did not
    run: the resolution was reached, committed, and read by a human as one
    coherent change, and the settlement put it on the pull request. What is
    left is the tail above, with the outcome the round actually had.

    `sync.ahead` is what says the commit reached the remote, and it is asked
    because the receipt cannot: a verdict that parked, or a human who moved
    the label by hand, leaves the same receipt over a commit still on disk
    only. Ahead of the remote the receipt stands and the recovered-commit push
    below carries it through the gate, which is the one road that measures it
    again -- and the tail clears the receipt wherever it finally runs.

    In sync is not the same claim as CARRYING it. A replacement host rebuilds
    the checkout from a pull request that has moved on, and what it gets is a
    branch level with its remote and standing on somebody else's head -- so
    the head the receipt names is proved against the checkout rather than
    inferred from the counters. That proof carries the remote with it: the
    caller fetched the branch before counting and refuses a checkout behind
    it, so a head that is in sync AND is the settled commit says the remote
    is standing there too.

    Fail closed on every other reading. A receipt whose head is not a whole
    object id is not one a checkout can be compared to, and a head this host
    cannot peel is not one anything may be compared against -- both leave the
    receipt exactly where it is for a tick that can prove it.
    """
    settled = _payloads.as_hex(
        ctx.state.get(_state._SETTLED_SHA), _formats.COMMIT_LENGTHS,
    )
    outcome = ctx.state.get(_state._SETTLED_OUTCOME)
    if not outcome or not settled or sync.ahead > 0 or pr_number is None:
        return False
    if not _standing_on(ctx, sync.worktree, settled):
        return False
    _hand_resolved_round_to_validating(
        ctx, conflict_round, pr_number, outcome=str(outcome), sha=settled,
    )
    return True


def _standing_on(
    ctx: _models._ConflictContext, worktree, settled: str,
) -> bool:
    """Whether this checkout is the commit a settled receipt names.

    Proved rather than read, because everything past it is a claim about one
    object id: a revision this host cannot peel is not a head that matches
    anything, and a host that never had the commit answers exactly that.
    """
    proved = _measurement_commits._prove_candidate_commit(worktree, _HEAD)
    if proved.is_frozen and proved.sha == settled:
        return True
    log.error(
        "issue=#%d stands on %s rather than the settled resolution %s; "
        "leaving the receipt for a tick that can prove it",
        ctx.issue.number, proved.sha or "an unreadable head", settled,
    )
    return False


def _forget_settled_round(ctx: _models._ConflictContext) -> None:
    """Drop a receipt the round it was owed for has now been paid on.

    Cleared by the tail rather than by the reader above, so a recovered-commit
    push that publishes a held resolution on its own -- reaching the tail
    under its own outcome -- leaves nothing behind for a later tick to finish
    a second time.
    """
    ctx.state.set(_state._SETTLED_OUTCOME, None)
    ctx.state.set(_state._SETTLED_SHA, None)
