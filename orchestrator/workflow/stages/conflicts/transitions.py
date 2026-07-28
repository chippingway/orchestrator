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

from typing import Optional

from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.engine import usage as _usage
from orchestrator.workflow.stages.conflicts import models as _models
from orchestrator.workflow.stages.conflicts import state as _state
from orchestrator.workflow.state import WorkflowLabel


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
    _emit_conflict_round_incremented(
        ctx,
        pr_number=int(pr_number),
        new_round=conflict_round + 1,
        outcome=outcome,
        sha=sha,
    )
    ctx.gh.set_workflow_label(ctx.issue, WorkflowLabel.VALIDATING)
    ctx.gh.write_pinned_state(ctx.issue, ctx.state)
