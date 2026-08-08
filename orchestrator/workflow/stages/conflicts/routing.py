# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two gates before a rebase may run, and the worktree it runs in.

The awaiting-human resume is asked first: an issue parked mid-rebase is waiting
on a person, and starting a fresh rebase under it would discard whatever the
dev was in the middle of. The `MAX_CONFLICT_ROUNDS` cap is asked next, and it
guards a loop that genuinely cannot converge on its own -- an unmergeable PR
that no amount of rebasing fixes would otherwise spawn a dev run every tick.

Preparing the worktree is where the reconciliation happens. The PR branch's
remote tip is re-fetched first because the ahead/behind measurement is only
meaningful against a current ref, and the three shapes it can report are
handled in the one order that is safe: refuse a behind-base divergence before
pushing anything, then ship recovered commits, then refresh base for the
rebase. A recovered push that leaves the branch still behind base falls through
to that rebase rather than ending the tick, so the two land as one round.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from orchestrator import config
from orchestrator.git.publication import probes as _publication_probes
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.workflow.stages.conflicts import divergence as _divergence
from orchestrator.workflow.stages.conflicts import guards as _guards
from orchestrator.workflow.stages.conflicts import models as _models
from orchestrator.workflow.stages.conflicts import rebase as _rebase
from orchestrator.workflow.stages.conflicts import resume as _resume
from orchestrator.workflow.stages.conflicts import state as _state
from orchestrator.workflow.stages.conflicts import transitions as _transitions


def _drive_conflict_rebase(
    ctx: _models._ConflictContext, pr, pr_number,
) -> None:
    """Route past the awaiting-human resume and the conflict cap, then prepare
    the worktree and rebase.

    Resume-on-human-reply comes first: when parked awaiting human and a new
    comment arrived, resume the dev session on the in-progress rebase worktree
    with the human's text (mirrors `_handle_implementing`'s awaiting-human
    path so a `_on_question` / `_on_dirty_worktree` park can be unstuck by a
    comment, as the park messages invite). The cap parks awaiting human once
    `MAX_CONFLICT_ROUNDS` rounds have failed.
    """
    conflict_round = int(ctx.state.get(_state._CONFLICT_ROUND) or 0)

    if ctx.state.get("awaiting_human"):
        _resume._resume_awaiting_human(ctx, conflict_round)
        return

    if conflict_round >= config.MAX_CONFLICT_ROUNDS:
        _transitions._park_conflict(
            ctx,
            f"{config.HITL_MENTIONS} auto-conflict-resolution still failing "
            f"after {conflict_round} round(s) "
            f"(`MAX_CONFLICT_ROUNDS={config.MAX_CONFLICT_ROUNDS}`); manual "
            "intervention needed.",
            reason="conflict_cap",
        )
        return

    wt = _prepare_conflict_worktree(ctx, pr, pr_number, conflict_round)
    if wt is None:
        return

    _rebase._rebase_and_dispose(ctx, pr_number, conflict_round, wt)


def _prepare_conflict_worktree(
    ctx: _models._ConflictContext, pr, pr_number, conflict_round: int,
) -> Optional[Path]:
    """Restore the worktree, refresh remote refs, and reconcile a diverged or
    crash-recovered branch before the base rebase.

    Returns the worktree to rebase, or ``None`` when the tick is fully handled
    (a fetch failure / diverged-branch / dirty park, or a crash-recovery push
    that flipped straight to `validating`) and the caller must return.
    """
    wt = _guards._ensure_conflict_worktree(ctx)
    branch = _worktree_paths._resolve_branch_name(
        ctx.state, ctx.spec, ctx.issue.number,
    )

    # Refresh `<remote>/<branch>` (the PR branch's remote tip) via the same
    # hardened authenticated path `_push_branch` uses. A stale local ref would
    # mis-classify a real "remote moved out from under us" as in-sync.
    if not _rebase._fetch_pr_branch(ctx, wt, branch):
        return None

    # Check the worktree against the freshly-fetched remote PR head. Three
    # shapes: in sync `(0, 0)` proceeds to the base rebase; HEAD ahead
    # `(>0, 0)` is the crash-recovery case (a prior tick committed a
    # resolution but crashed before the push / post-push state write landed);
    # anything `behind > 0` is a stale or diverged worktree we refuse to
    # force-push over.
    sync = _models._WorktreeSync(
        wt, branch,
        *_publication_probes._branch_ahead_behind(ctx.spec, wt, branch),
    )
    guard = _divergence._guard_diverged_worktree(ctx, pr, sync)
    if guard.parked:
        return None
    if sync.ahead > 0 and _divergence._push_recovered_commits(
        ctx, sync, conflict_round, pr_number, guard.publish_lease,
    ):
        return None

    # In sync (or fell through after a recovered push to reconcile a stale
    # base). Refresh `<remote>/<base>` so the upcoming rebase sees the current
    # base tip.
    if not _rebase._fetch_base_ref(ctx, wt):
        return None
    return wt
