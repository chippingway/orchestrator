# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The terminal answers a verified crash-recovery comparison can produce.

One interrupted auto-rebase resolves into exactly one of these: the rewrite
was already published, the comparison is unclassifiable, the remote moved
out of band, the worktree is dirty, the reissued push failed, the pinned
comment claims an exemption or a transfer nobody can read whole, the attempt's
own record is in pieces, the attempt was made for a publication this issue no
longer records, the remote was rolled back off a replay the record says it
carried, or a rewrite the pull request already carries is one this tick cannot
finish the route behind.
Each one either finalizes through ``persistence`` or parks, so keeping them
in one owner is what makes the set enumerable -- an outcome that neither
routed nor parked would leave the issue holding an anchor no later tick can
act on.

Most parks reset HEAD onto the pre-rebase anchor first, because that anchor
is the head the remote PR still carries and the reviewer is still voting on.
Two must not. The unfinished-route park sits over a remote standing on the
REWRITE, so putting the branch back on the anchor would take the checkout off
work the pull request has. And the foreign-publication park cannot say which
pull request the branch belongs to at all, which is a question about the
issue's record rather than about the commit -- throwing the replay away would
answer neither. Both park with the anchor left pinned instead, and the next
tick classifies afresh.
"""
from __future__ import annotations

from orchestrator import config
from orchestrator.git.base_sync import persistence, snapshot
from orchestrator.git.base_sync.models import (
    _AutoRebaseRecoveryContext,
    _AutoRebaseRecoverySnapshot,
)
from orchestrator.git.base_sync.state import (
    _REASON_AUTO_BASE_REBASE_FAILED,
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


def _park_unfinished_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
    detail: str,
) -> bool:
    """Park, without a reset, a landed rewrite this tick may not finish.

    The pull request is standing on the rewritten commit and so is the
    checkout, so there was never anything to send here: what the tick owed was
    a receipt, a settlement, or nothing at all -- and it could not establish
    which. `detail` is the reason it could not, and it is the operator's whole
    starting point.

    HEAD is deliberately left alone. Every other park here resets onto the
    pre-rebase anchor because that is the head the remote still carries; here
    the remote carries the rewrite instead, so a reset would take the checkout
    off work the pull request has and hand the next reader a branch behind its
    own publication.

    The anchor stays pinned with it, and that is what makes the park
    recoverable rather than terminal. It is also the whole reason this park
    exists rather than the ordinary relabel: the anchor is the only thing that
    brings this recovery back, so clearing it over a verdict that may not have
    moved leaves the next tick to measure a rewrite a human already ruled on
    and route it into adjudication a second time. A human's reply re-enters
    this route, the remote is read again, and whatever it turns out to be is
    classified from scratch.
    """
    local_short = (recovery_snapshot.local_head or "")[:8]
    log.warning(
        "issue=#%d auto-rebase recovery: PR #%d already carries %s and this "
        "tick cannot finish the route behind it (%s); leaving HEAD and the "
        "recovery anchor exactly as they are and parking awaiting human",
        context.issue.number, context.pr_number, local_short, detail,
    )
    persistence._park_auto_rebase_failure(
        context.gh,
        context.issue,
        context.state,
        message=(
            f"{config.HITL_MENTIONS} crash recovery for PR "
            f"#{context.pr_number}: the branch was rebased and pushed before "
            f"an earlier tick died, so PR #{context.pr_number} already "
            f"carries `{local_short}` -- but the route behind that push "
            f"cannot be finished safely because {detail}. HEAD has NOT been "
            "reset: the worktree is standing on the commit the PR carries. "
            "Investigate the pinned comment and the remote branch, then reply "
            "on this issue with anything once they are reconciled."
        ),
        reason=_REASON_AUTO_BASE_REBASE_PUSH_FAILED,
    )
    return True


def _park_unvouched_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Restore the anchor rather than measure a record nobody can read.

    The comment claims something about the commit this issue exempts -- a
    transfer group short of a member, an exemption it cannot show whole, an
    identity taken under a scheme this build does not compute -- and the
    branch is standing on a replay of that commit with nothing on the remote
    yet.

    Every other road from here ends in the ordinary cumulative gate, and for
    an adjudicated change that is the wrong answer twice over: the replay is
    measured past the same ceiling and routed into a second adjudication, with
    a pull request already open over the work, on the strength of a record
    nothing checked. The permit refuses the same claim for the same reason, so
    there is nothing this tick could do with it but ask.

    So the branch goes back onto the anchor -- the head the remote still
    carries, so nothing is lost that the reflog does not have -- and the issue
    parks. The record itself is left exactly as it stands: a group this reader
    cannot vouch for is the only account there is of how the exemption came to
    name what it names, and the rollback drops only what it can read whole.
    """
    local_short = (recovery_snapshot.local_head or "")[:8]
    pre_rebase_short = context.pending_pre_rebase_sha[:8]
    log.warning(
        "issue=#%d auto-rebase recovery: the pinned comment claims a transfer "
        "for the commit this issue exempts and this build cannot read it back "
        "whole; resetting %s onto the anchor and parking rather than measuring "
        "an adjudicated change again",
        context.issue.number, local_short,
    )
    persistence._reset_clear_and_park(
        context,
        context.pending_pre_rebase_sha,
        message=(
            f"{config.HITL_MENTIONS} crash recovery for PR "
            f"#{context.pr_number}: this issue's pinned comment claims an "
            "adjudication exemption -- or a transfer of one -- that the "
            "orchestrator cannot read back whole, and the interrupted rebase "
            f"left `{local_short}` on the branch. Publishing it would send a "
            "change a human already ruled on back into adjudication on the "
            "strength of a record nothing could check, so HEAD has been reset "
            f"to the pre-rebase SHA `{pre_rebase_short}` and nothing was "
            "pushed. Repair the `late_exempt_*` / `late_rewrite_*` fields on "
            "the pinned comment, then reply on this issue with anything to "
            "retry."
        ),
        reason=_REASON_AUTO_BASE_REBASE_FAILED,
    )
    return True


def _park_rolled_back_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Restore the anchor when the remote was rolled back off this replay.

    The record says the pull request carried the commit on this checkout --
    a receipt naming it, or a transfer that settled on the write behind one --
    and the remote is not standing on it now. Somebody moved the branch back,
    and where they moved it to is very often the pre-rebase anchor itself,
    which is the head a reissued force-push would be leased against. That
    lease would be satisfied, the push would land, and the rollback would be
    gone -- the one outcome a lease exists to prevent, reached by a recovery
    mistaking somebody's undo for its own unfinished work.

    So it is the externally moved remote it is: HEAD goes back onto the anchor
    so the checkout matches what the pull request has, the anchor is dropped
    with it, and the issue parks for a human to say which of the two heads the
    branch is supposed to be on.
    """
    local_short = (recovery_snapshot.local_head or "")[:8]
    remote_short = (recovery_snapshot.remote_head or "")[:8]
    log.warning(
        "issue=#%d auto-rebase recovery: the pinned comment records %s as "
        "published and PR #%d stands on %s; treating the branch as rolled "
        "back out of band rather than force-pushing over it",
        context.issue.number, local_short, context.pr_number, remote_short,
    )
    persistence._reset_clear_and_park(
        context,
        context.pending_pre_rebase_sha,
        message=(
            f"{config.HITL_MENTIONS} crash recovery for PR "
            f"#{context.pr_number}: this issue's pinned comment records "
            f"`{local_short}` as already pushed, and the pull request is "
            f"standing on `{remote_short}` instead -- the branch was rolled "
            "back or moved out of band while the orchestrator was down. "
            "Reissuing the interrupted push would be leased against the very "
            "head it was rolled back to and would overwrite it, so nothing "
            "was pushed and HEAD has been reset to the pre-rebase SHA. "
            "Investigate the remote branch and reply on this issue with "
            "anything once it is reconciled."
        ),
        reason=_REASON_AUTO_BASE_REBASE_PUSH_FAILED,
    )
    return True


def _park_foreign_publication_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Park, without a reset, an attempt made for another publication.

    The interrupted tick recorded which pull request it rebased for and which
    stage it was entered from, and the issue no longer says either. Every road
    out of a recovery ends in the same tail -- a notice to the pull request
    this tick holds, an audit event filed under the stage this tick reads, and
    the anchor dropped -- so finishing here would attribute the dead tick's
    work to a publication it was never made for, and drop the one record that
    could ever say otherwise.

    Nothing is reset. Which publication the branch belongs to is exactly what
    this tick cannot say, and putting the checkout back onto the anchor would
    throw the replay away to settle a question about the pull request rather
    than about the commit. The whole record stays pinned with it, so a human
    who repoints the issue back, or clears the record, hands the next tick
    something it can finish.
    """
    recorded = context.pending_rewrite
    log.warning(
        "issue=#%d auto-rebase recovery: the interrupted attempt recorded PR "
        "#%d from %r and this issue now records PR #%d on %r; parking rather "
        "than finishing a route for a publication it was not made for",
        context.issue.number, recorded.pr_number, str(recorded.stage),
        context.pr_number, str(context.label),
    )
    persistence._park_auto_rebase_failure(
        context.gh,
        context.issue,
        context.state,
        message=(
            f"{config.HITL_MENTIONS} crash recovery for this issue's auto "
            f"rebase: the interrupted attempt was made against pull request "
            f"#{recorded.pr_number} from `{recorded.stage}`, and this issue "
            f"now records pull request #{context.pr_number} on "
            f"`{context.label}`. Finishing it would post the notice, file the "
            "audit event, and route the reviewer against a publication that "
            "attempt was never made for, so nothing was pushed and HEAD has "
            "not been reset. Put the issue back on the publication the rebase "
            "was made for -- or clear the "
            "`pending_auto_base_rebase_*` fields on the pinned comment -- then "
            "reply on this issue with anything to retry."
        ),
        reason=_REASON_AUTO_BASE_REBASE_FAILED,
    )
    return True


def _park_unrecorded_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Restore the anchor when the attempt's own record is in pieces.

    The pinned comment claims a record of what this attempt produced and
    cannot show it whole -- a member missing, a pull request that is not an
    identity, a stage no publication is entered from. Read as the absence it
    resembles, the recovery would fall through to the ahead/behind counts and
    a strictly-ahead checkout would be measured and force-pushed on the
    strength of a claim nothing could check.

    So the branch goes back onto the anchor, which is the head the remote
    still carries wherever this refusal is reachable, and the issue parks. The
    record itself is left where the reset's own rule leaves every damaged
    group: for a human to repair, not for this tick to guess at.
    """
    local_short = (recovery_snapshot.local_head or "")[:8]
    pre_rebase_short = context.pending_pre_rebase_sha[:8]
    log.warning(
        "issue=#%d auto-rebase recovery: the record of what this attempt "
        "produced is not one this build can read whole; resetting %s onto the "
        "anchor rather than publishing a checkout nothing vouches for",
        context.issue.number, local_short,
    )
    persistence._reset_clear_and_park(
        context,
        context.pending_pre_rebase_sha,
        message=(
            f"{config.HITL_MENTIONS} crash recovery for PR "
            f"#{context.pr_number}: the pinned comment claims a record of the "
            "rebase an earlier tick was interrupted in the middle of, and the "
            "orchestrator cannot read it back whole -- so it cannot say that "
            f"`{local_short}` on the branch is that attempt's own work. HEAD "
            f"has been reset to the pre-rebase SHA `{pre_rebase_short}` and "
            "nothing was pushed. Repair or clear the "
            "`pending_auto_base_rebase_*` fields on the pinned comment, then "
            "reply on this issue with anything to retry."
        ),
        reason=_REASON_AUTO_BASE_REBASE_FAILED,
    )
    return True
