# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A body edit during the final-docs hop, and the unwind it forces.

The reviewer approved the OLD requirements, so a docs pass started after the
edit would document a body the reviewer never saw. The stage does not try to
absorb that: it drops the stale approval, hands the worktree to `drift_reset`,
and routes the issue back to `validating` for a re-review. No docs agent runs
-- a commit on top of a dead approval would only have to be re-reviewed
alongside whatever the new body changes.

Two orderings carry the whole contract. `review_round` is cleared BEFORE any
fallible git step, because drift invalidates the approval whether or not the
on-disk reset succeeds -- an operator unpark after a failed fetch must not be
able to ride the stale round counter into a handoff that skips the re-review.
And `docs_drift_unwind_pending` is seeded at the same moment and cleared only on
the relabel, so a reconcile that parked is re-entered on the next tick instead
of falling through to the normal flow and advancing to `in_review` against the
old body. That re-entry is why a pending unwind with nothing fresh to act on
returns silently: only a trusted reply is the "retry it" signal, and without
that guard the same park comment would repost on every poll.
"""
from __future__ import annotations

from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.github.comments import filter_trusted
from orchestrator.workflow.engine import (
    comments as _comments,
    drift as _engine_drift,
)
from orchestrator.workflow.stages.documenting import (
    drift_reset as _drift_reset,
    models as _models,
    state as _state,
)
from orchestrator.workflow.state import WorkflowLabel


def _announce_documenting_drift(
    ctx: _models._DocumentingContext, new_hash: str,
) -> None:
    """Record the new body hash, post the re-route notice, and mark the
    issue-thread comments consumed for a freshly-detected drift."""
    ctx.state.set("user_content_hash", new_hash)
    _comments._post_issue_comment(
        ctx.gh, ctx.issue, ctx.state,
        ":pencil2: issue body changed; routing back to "
        "`validating` so the reviewer re-evaluates the "
        "updated requirements.",
    )
    _engine_drift._mark_drift_comments_consumed(ctx.gh, ctx.issue, ctx.state)


def _begin_documenting_drift_unwind(ctx: _models._DocumentingContext) -> None:
    """Seed the drift-unwind sentinel and drop the stale approval.

    Set `docs_drift_unwind_pending` so an operator unpark or a later human
    comment (without a fresh drift) re-enters the drift block on the next tick
    and retries the reconcile + relabel; the marker is cleared ONLY on the
    success path that relabels to `validating`. Without it, an operator unpark
    on a failed reconcile would fall through to the normal flow and advance to
    `in_review` against the OLD body, skipping the required `validating`
    re-review.

    Clear `review_round` BEFORE any fallible cleanup (fetch / reset): drift
    means the prior reviewer approval is stale regardless of whether the
    on-disk reset succeeds, so the round counter must drop now -- an operator
    unpark or manual relabel after a fetch failure must not be able to ride
    the stale approval into a final-docs handoff that skips the re-review.
    """
    state = ctx.state
    state.set("docs_drift_unwind_pending", True)
    state.set(_state._AWAITING_HUMAN, False)
    state.set(_state._PARK_REASON, None)
    state.set("review_round", 0)


def _reconcile_documenting_drift(ctx: _models._DocumentingContext) -> bool:
    """Docs drift detection + unwind back to `validating`.

    User-content drift: a human edited the issue title/body while the
    final-docs hop was in flight. The reviewer approved the OLD
    requirements, so the docs pass would be running against a body the
    reviewer never saw. Mirror `_handle_in_review`'s drift invalidation:
    reset `review_round=0`, post the notice, mark issue-thread comments
    consumed, refresh the baseline hash, reconcile the worktree, and
    relabel to `validating` so the reviewer re-evaluates the updated body
    on the next tick. Do NOT spawn the docs agent: the prior approval is
    gone and a docs commit on top would just need to be re-reviewed
    alongside any impl change.

    Returns True when the drift path fully handled this tick (the silent
    fast-path, a reconcile park, or the relabel to `validating`); False
    when there is no drift and the normal docs flow should continue.
    """
    new_hash = _engine_drift._detect_user_content_change(
        ctx.gh, ctx.issue, ctx.state,
    )
    fresh_drift = new_hash is not None
    pending_unwind = bool(ctx.state.get("docs_drift_unwind_pending"))
    # A prior tick's drift unwind couldn't finish (the worktree reconcile
    # failed and parked) and nothing fresh has happened: stay silent so the
    # parked state survives operator inspection without re-posting the same
    # park comment every tick. Only a trusted reply is the "retry the unwind"
    # signal -- with `ALLOWED_ISSUE_AUTHORS` set an outsider comment must not
    # fall through to the reconcile-retry below.
    if pending_unwind and not fresh_drift and ctx.state.get(_state._AWAITING_HUMAN):
        last_action_id = ctx.state.get(_state._LAST_ACTION_COMMENT_ID)
        if not filter_trusted(ctx.gh.comments_after(ctx.issue, last_action_id)):
            return True
    if not (fresh_drift or pending_unwind):
        return False

    if fresh_drift:
        _announce_documenting_drift(ctx, new_hash)
    _begin_documenting_drift_unwind(ctx)
    wt = _worktree_paths._worktree_path(ctx.spec, ctx.issue.number)
    if wt.exists() and not _drift_reset._reset_documenting_drift_worktree(ctx, wt):
        return True
    # Reconcile succeeded (or the worktree didn't exist): the drift unwind is
    # complete, clear the sentinel and relabel.
    ctx.state.set("docs_drift_unwind_pending", False)
    ctx.gh.set_workflow_label(ctx.issue, WorkflowLabel.VALIDATING)
    ctx.gh.write_pinned_state(ctx.issue, ctx.state)
    return True
