# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The terminal answers a verified crash-recovery comparison can produce.

One interrupted auto-rebase resolves into exactly one of these: the rewrite
was already published, the comparison is unclassifiable, the remote moved
out of band, the worktree is dirty, the reissued push failed, or the leased
no-op that would have receipted an already-published rewrite was refused.
Each one either finalizes through ``persistence`` or parks, so keeping them
in one owner is what makes the set enumerable -- an outcome that neither
routed nor parked would leave the issue holding an anchor no later tick can
act on.

Four of the five parks reset HEAD onto the pre-rebase anchor first, because
that anchor is the head the remote PR still carries and the reviewer is still
voting on. The refused no-op is the one that must not: the remote is standing
on the REWRITE there, so putting the branch back on the anchor would take the
checkout off work the pull request has. It parks with the anchor left pinned
instead, and the next tick classifies the remote afresh.
"""
from __future__ import annotations

from orchestrator import config
from orchestrator.git.base_sync import persistence, snapshot
from orchestrator.git.base_sync.models import (
    _AutoRebaseRecoveryContext,
    _AutoRebaseRecoverySnapshot,
)
from orchestrator.git.base_sync.state import (
    _REASON_AUTO_BASE_REBASE_PUSH_FAILED,
    log,
)
from orchestrator.workflow.state import WorkflowLabel


def _already_published_recovery_notice(
    context: _AutoRebaseRecoveryContext,
    local_head: str,
) -> str:
    """Format the notice for a recovery push that landed before restart."""
    short_head = local_head[:8]
    notice = (
        f":mag: Recovered an interrupted auto-rebase for PR "
        f"#{context.pr_number}; the new head `{short_head}` was "
        "already published before the orchestrator restart."
    )
    if context.behind == 0:
        return (
            notice
            + f" Routing `{context.label}` -> `{WorkflowLabel.VALIDATING}`"
            " so the reviewer re-runs against the rewritten branch."
        )
    return (
        notice
        + f" Base advanced again by {context.behind} commit(s)"
        " since the interrupted rebase; rebasing once more before "
        f"routing to `{WorkflowLabel.VALIDATING}`."
    )


def _pushed_recovery_notice(
    context: _AutoRebaseRecoveryContext,
    local_head: str,
) -> str:
    """Format the notice for a recovery push reissued this tick."""
    short_head = local_head[:8]
    notice = (
        f":mag: Recovered an interrupted auto-rebase for PR "
        f"#{context.pr_number}; pushed the recovered head "
        f"`{short_head}`."
    )
    if context.behind == 0:
        return (
            f"{notice} Routing `{context.label}` -> "
            f"`{WorkflowLabel.VALIDATING}`."
        )
    return (
        notice
        + f" Base advanced again by {context.behind} commit(s) "
        "since the interrupted rebase; rebasing once more before "
        f"routing to `{WorkflowLabel.VALIDATING}`."
    )


def _finalize_already_published_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Finalize state after confirming that the interrupted push landed."""
    return persistence._finalize_recovered_rebase(
        context,
        local_head=recovery_snapshot.local_head,
        method="crash_recovery_relabel_only",
        notice=_already_published_recovery_notice(
            context, recovery_snapshot.local_head,
        ),
    )


def _reject_unknown_recovery_comparison(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Park when unequal heads cannot be classified as ahead or behind."""
    log.warning(
        "issue=#%d auto-rebase recovery: local HEAD (`%s`) differs "
        "from remote PR head (`%s`) but the divergence probe "
        "returned `(0, 0)`; aborting recovery and parking awaiting "
        "human",
        context.issue.number,
        recovery_snapshot.local_head[:8],
        recovery_snapshot.remote_head[:8],
    )
    local_short = recovery_snapshot.local_head[:8]
    remote_short = recovery_snapshot.remote_head[:8]
    return snapshot._abort_recovery_unverified(
        context,
        f"local HEAD `{local_short}` differs from remote "
        f"PR head `{remote_short}` but "
        "the divergence probe returned `(0, 0)`, which means the "
        "remote-tracking ref we just fetched could not be read or "
        "compared against -- the path the recovery would take next "
        "cannot be determined safely.",
    )


def _park_diverged_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Restore the anchor instead of overwriting an out-of-band PR update."""
    spec = context.spec
    local_short = recovery_snapshot.local_head[:8]
    pre_rebase_short = context.pending_pre_rebase_sha[:8]
    persistence._reset_clear_and_park(
        context,
        context.pending_pre_rebase_sha,
        message=(
            f"{config.HITL_MENTIONS} crash recovery for PR "
            f"#{context.pr_number}: local worktree "
            f"(`{local_short}`) is {recovery_snapshot.ahead} ahead "
            f"and {recovery_snapshot.behind} behind remote "
            f"`{spec.remote_name}/{recovery_snapshot.branch}` -- the "
            "remote PR branch was updated out-of-band during the "
            "interrupted auto rebase. HEAD has been reset to the pre-"
            f"rebase SHA `{pre_rebase_short}`. "
            "Investigate the remote PR head and reply on this issue "
            "with anything once the divergence is reconciled."
        ),
        reason=_REASON_AUTO_BASE_REBASE_PUSH_FAILED,
    )
    return True


def _park_dirty_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
    dirty_files: list[str],
) -> bool:
    """Reset and clean a recovered rebase that carries worktree changes."""
    local_short = recovery_snapshot.local_head[:8]
    pre_rebase_short = context.pending_pre_rebase_sha[:8]
    persistence._reset_clear_and_park(
        context,
        context.pending_pre_rebase_sha,
        message=(
            f"{config.HITL_MENTIONS} crash recovery for PR "
            f"#{context.pr_number}: the rebased worktree (recovered "
            f"from a prior tick, HEAD `{local_short}`) "
            f"carries {len(dirty_files)} uncommitted change(s). HEAD "
            "has been reset to the pre-rebase SHA "
            f"`{pre_rebase_short}` and untracked "
            "files cleaned (use `git reflog` if you need the "
            "discarded edits). Investigate, then reply on this issue "
            "with anything to retry."
        ),
        reason="auto_base_rebase_dirty",
        clean=True,
    )
    return True


def _park_failed_recovery_push(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Restore the anchor after a recovered force-push fails."""
    local_short = recovery_snapshot.local_head[:8]
    pre_rebase_short = context.pending_pre_rebase_sha[:8]
    persistence._reset_clear_and_park(
        context,
        context.pending_pre_rebase_sha,
        message=(
            f"{config.HITL_MENTIONS} crash recovery for PR "
            f"#{context.pr_number}: `--force-with-lease` push of the "
            f"recovered rebase (`{local_short}`, lease "
            f"against `{pre_rebase_short}`) failed. "
            "HEAD has been reset to the pre-rebase SHA. Most likely "
            "the remote PR branch was updated out-of-band; investigate "
            "and reply on this issue with anything to retry."
        ),
        reason=_REASON_AUTO_BASE_REBASE_PUSH_FAILED,
    )
    return True


def _park_unsettled_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Park, without a reset, when the receipting no-op is refused.

    The pull request is standing on the rewritten commit and the checkout is
    standing on it too, so this recovery had nothing to send: the push was the
    leased proof that the remote is still where the interrupted tick left it.
    Refused, that proof failed -- somebody moved the branch between this
    tick's fetch and the request -- and what the tick may not do is act on
    either reading.

    HEAD is deliberately left alone. Every other park here resets onto the
    pre-rebase anchor because that is the head the remote still carries; here
    the remote carries the rewrite instead, so a reset would take the checkout
    off work the pull request has and hand the next reader a branch behind its
    own publication.

    The anchor stays pinned with it, which is what makes the park recoverable
    rather than terminal: a human's reply re-enters this route, the remote is
    read again, and whatever it turns out to be is classified from scratch.
    """
    local_short = (recovery_snapshot.local_head or "")[:8]
    log.warning(
        "issue=#%d auto-rebase recovery: the leased no-op that would have "
        "receipted the already-published %s was refused; leaving HEAD and the "
        "recovery anchor exactly as they are and parking awaiting human",
        context.issue.number, local_short,
    )
    persistence._park_auto_rebase_failure(
        context.gh,
        context.issue,
        context.state,
        message=(
            f"{config.HITL_MENTIONS} crash recovery for PR "
            f"#{context.pr_number}: the branch was rebased and pushed before "
            f"an earlier tick died, so PR #{context.pr_number} already "
            f"carries `{local_short}` -- but the `--force-with-lease` no-op "
            "that would have recorded it (leased against that same commit) "
            "was refused, which means the remote branch moved after this "
            "tick read it. HEAD has NOT been reset: the worktree is standing "
            "on the commit the PR was carrying. Investigate the remote branch "
            "and reply on this issue with anything once it is reconciled."
        ),
        reason=_REASON_AUTO_BASE_REBASE_PUSH_FAILED,
    )
    return True
