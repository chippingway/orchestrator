# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The single route from an interrupted auto-rebase to one terminal answer.

The verified facts arrive from ``snapshot`` and the answers live in
``outcomes``; what this owner adds is the order they are asked in, and that
order is the safety property. An ineligible label is cleared before anything
is fetched, an unmoved HEAD falls back to the normal rebase flow before any
comparison is trusted, and equality with the remote is checked before the
ahead/behind counts are -- so the reissued force-push is only ever reached by
a head proven to be ahead of a remote the tick actually read. Anything else
parks. The legacy keyword signature is bound here too, because the flat
callers still pass the pre-context argument list this route derives its
context from.

What the remote says is only half of what an interrupted rebase has to be
classified by, because the rebase may have been carrying a human's verdict
onto the commit it produced. ``transfers`` answers the other half off the
pinned comment -- how far the transfer's own writes got -- and the two roads
that still publish something are handed it. A rewrite the grant never reached
is given re-derived evidence, so the replay is decided on the transfer the
dead tick would have asked for rather than measured past the same ceiling; a
push that landed with its receipt lost is settled here, on the stage the
permit was granted under, through the leased no-op that proves the pull
request really carries it. Every state neither of those covers -- a record
this build cannot read, a tree carrying uncommitted changes, a remote
somebody moved -- keeps the fail-closed park or reset it always had.
"""
from __future__ import annotations

import inspect
from typing import Any

from orchestrator.git.base_sync import (
    outcomes,
    persistence,
    publication,
    snapshot,
    transfers,
)
from orchestrator.git.base_sync.models import (
    _AutoRebaseRecoveryContext,
    _AutoRebaseRecoverySnapshot,
)
from orchestrator.git.base_sync.state import _PR_REFRESH_DETOUR_LABELS
from orchestrator.git.verification import probes as verification_probes

# Why a landed rewrite's route could not be finished, in the operator's own
# terms. Spelled at the two seams that answer for them rather than beside the
# park, which takes whatever reason its caller established.
_LOOSE_TREE = (
    "the worktree carries {count} uncommitted change(s), so the contribution "
    "the transfer would be settled over is not the one the pull request has"
)

_REFUSED_NO_OP = (
    "the `--force-with-lease` no-op that would have recorded it, leased "
    "against that same commit, was refused -- the remote branch moved after "
    "this tick read it"
)

_RECOVERY_SIGNATURE = inspect.Signature((
    inspect.Parameter("gh", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("spec", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("issue", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("state", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("worktree", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("pr_number", inspect.Parameter.KEYWORD_ONLY),
    inspect.Parameter("label", inspect.Parameter.KEYWORD_ONLY),
    inspect.Parameter(
        "pending_pre_rebase_sha",
        inspect.Parameter.KEYWORD_ONLY,
    ),
    inspect.Parameter("behind", inspect.Parameter.KEYWORD_ONLY, default=0),
    inspect.Parameter(
        "unparking_consumed_max",
        inspect.Parameter.KEYWORD_ONLY,
        default=None,
    ),
))


def _retry_recovery_push(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
    carried: transfers._Handoff = transfers._Handoff.NOTHING,
) -> bool:
    """Publish a verified ahead-only recovery head and finalize its state.

    Measured before it is published, like every other push onto a pull request
    the remote already carries: the head this recovery found is one an earlier
    tick rebased and never pushed, so nothing on this branch has been read
    against the base it now sits on.

    Unless the branch is standing on a rewrite of a commit an adjudication
    accepted, which is the one candidate that may be published without a
    reading. `carried` says how far the interrupted tick got with that
    transfer, and what this call owes it is only the evidence: a permission
    the grant already recorded is what `late_transfer` re-asks the permit
    over, and a rewrite that never reached one is re-derived here so the
    replay is not measured past the same ceiling and adjudicated a second
    time with a pull request open over the work.
    """
    dirty_files = verification_probes._worktree_dirty_files(context.worktree)
    if dirty_files:
        return outcomes._park_dirty_recovery(
            context, recovery_snapshot, dirty_files,
        )
    records = publication._gate_records()
    published = publication._gated_publication()._publishes(
        records._gate(
            context.gh, context.spec, context.issue, context.state,
            context.worktree,
        ),
        recovery_snapshot.branch,
        records._Entered(
            head=context.pending_pre_rebase_sha or "", reconciling=True,
            # The head this recovery verified against the remote and the one
            # the finalize below records as published. The gate proves the
            # checkout again, and a commit that landed between the two
            # readings would be the one pushed while the notice and the event
            # named this one -- so the candidate is bound and a moved checkout
            # refuses instead.
            candidate=recovery_snapshot.local_head or "",
            rewrite=transfers._reconstructed(
                context, recovery_snapshot.local_head or "", carried,
            ),
        ),
    )
    if published.held:
        # The gate took the candidate this recovery was finishing, so the
        # finalize below -- the notice, the event, the `validating` route --
        # is not this tick's. The park it left is written here, since nothing
        # behind this call would.
        context.gh.write_pinned_state(context.issue, context.state)
        return True
    if not published.landed:
        return outcomes._park_failed_recovery_push(context, recovery_snapshot)
    return persistence._finalize_recovered_rebase(
        context,
        local_head=recovery_snapshot.local_head,
        method="crash_recovery_pushed",
        notice=outcomes._pushed_recovery_notice(
            context, recovery_snapshot.local_head,
        ),
    )


def _finish_published_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
    carried: transfers._Handoff = transfers._Handoff.NOTHING,
) -> bool:
    """Finish the route behind a rewrite the pull request already carries.

    The ordinary answer is a relabel and nothing else: the push landed before
    the crash, the remote has the commit, and what the dead tick still owed
    was the notice, the audit event, and the reviewer's route back. Nothing is
    pushed, nothing is measured, and no agent runs -- which is exactly what an
    already-landed rewrite has to get.

    One handoff owes more, and it is the window between a push that landed and
    the write that receipts it. There the permission a transfer was granted on
    is still OUTSTANDING: the exemption is on the commit a human ruled on, the
    debt still says a push is owed, and nothing on the comment says the pull
    request carries the rewrite. Relabelled and left, that permission is
    re-asked one stage later against a `validating` issue the rewrite was
    never entered from -- the permit refuses on the stage alone, the ordinary
    cumulative gate measures the replay, and an adjudicated change is routed
    back into adjudication.

    So the settlement is taken HERE, on the tick and the stage the transfer
    was granted under, and it is taken through the same gated publication
    every other push in this domain goes through. Standing on the commit
    already, that publication is the leased no-op the push tail makes anyway:
    nothing is sent, the lease is the rewritten commit itself, and what it
    buys is the receipt, the paid debt, and the rotation riding one durable
    write -- proved at the remote rather than read off a local note.

    Every other handoff is asked whether the pinned comment ACCOUNTS for the
    rewrite the pull request carries, and only an accounted one is finished.
    An issue carrying no verdict always is, which is the ordinary interrupted
    rebase and the whole of what this road used to be. One whose transfer
    settled, or whose replay the ordinary cumulative gate published, is
    accounted for by the receipt that write left. Anything else -- a record
    this build cannot read, a receipt nobody wrote, a debt nothing paid --
    parks with the anchor still pinned, because finishing there would drop the
    one thing that brings this recovery back and leave the next tick to
    measure an adjudicated change as a fresh candidate.
    """
    if carried == transfers._Handoff.OUTSTANDING:
        return _settles_the_landed_rewrite(context, recovery_snapshot)
    unaccounted = transfers._unaccounted_publication(
        context.state, recovery_snapshot.local_head or "", carried,
    )
    if unaccounted:
        return outcomes._park_unfinished_recovery(
            context, recovery_snapshot, unaccounted,
        )
    return outcomes._finalize_already_published_recovery(
        context, recovery_snapshot,
    )


def _settles_the_landed_rewrite(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Take the settlement a landed push still owes, or park for the tree.

    The permission is outstanding and the commit it names is the one the pull
    request carries, so what is missing is the receipt -- and taking it is
    what stops the permit being re-asked one stage later, against an issue the
    rewrite was never entered from.

    A checkout carrying uncommitted changes may not be settled over: the
    contribution the permit is re-derived from is fingerprinted in that tree,
    and one carrying work nobody committed is not the contribution the pull
    request has. Nothing is reset for it -- the remote is right and so is the
    branch -- but the route is not finished either, because clearing the
    anchor over an exemption still on the old commit is what sends the replay
    back into adjudication.
    """
    dirty_files = verification_probes._worktree_dirty_files(context.worktree)
    if not dirty_files:
        return _settle_published_recovery(context, recovery_snapshot)
    return outcomes._park_unfinished_recovery(
        context, recovery_snapshot,
        _LOOSE_TREE.format(count=len(dirty_files)),
    )


def _settle_published_recovery(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Receipt a landed rewrite through the leased no-op that proves it.

    Entered on the pre-rebase anchor and named against the rewritten commit,
    exactly as the interrupted tick entered it: the anchor is the head the
    permit was granted against, and the pull request standing on the rewrite
    instead is a head that permit accounts for while its permission is
    outstanding -- this issue's own push having landed, with only the receipt
    behind it lost.

    A refused push is the one thing that can still go wrong, and it is a
    remote that moved between this tick's fetch and the request. Nothing is
    reset for it: the checkout is standing on the commit the pull request was
    carrying a moment ago, and putting it back on the anchor would take the
    branch off work the remote has. The anchor stays pinned, the issue parks,
    and the next recovery classifies the remote afresh.
    """
    records = publication._gate_records()
    published = publication._gated_publication()._publishes(
        records._gate(
            context.gh, context.spec, context.issue, context.state,
            context.worktree,
        ),
        recovery_snapshot.branch,
        records._Entered(
            head=context.pending_pre_rebase_sha or "", reconciling=True,
            candidate=recovery_snapshot.local_head or "",
        ),
    )
    if published.held:
        context.gh.write_pinned_state(context.issue, context.state)
        return True
    if not published.landed:
        return outcomes._park_unfinished_recovery(
            context, recovery_snapshot, _REFUSED_NO_OP,
        )
    return outcomes._finalize_already_published_recovery(
        context, recovery_snapshot,
    )


def _recover_pending_auto_base_rebase_context(
    context: _AutoRebaseRecoveryContext,
) -> bool:
    """Route an interrupted auto-rebase from verified local/remote state."""
    if context.label not in _PR_REFRESH_DETOUR_LABELS:
        return snapshot._clear_ineligible_recovery(context)

    recovery_snapshot = snapshot._fetch_recovery_snapshot(context)
    if recovery_snapshot is None:
        return True
    if (
        recovery_snapshot.local_head
        and recovery_snapshot.local_head == context.pending_pre_rebase_sha
    ):
        return snapshot._clear_unchanged_recovery(context)

    return _route_recovery_snapshot(context, recovery_snapshot)


def _route_recovery_snapshot(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Route a changed-head recovery from its completed local/remote compare.

    Two classifications rather than one, taken together because the answer is
    the pair. Where the REMOTE stands says which effect the dead tick got as
    far as -- still on the anchor and the push never went out, on the rewrite
    and it did, anywhere else and somebody moved the branch out of band. What
    the pinned comment CARRIES says which of the transfer's own writes it got
    as far as, and that is what the two roads with something left to publish
    are handed: the evidence a permit is decided on, and whether the receipt
    behind a landed push is still owed.

    The transfer is read once, before either road, because it costs nothing
    and because reading it twice would let the two roads disagree about the
    same comment.

    Both halves of the remote question are answered by the exact SHA rather
    than by the ahead/behind counts, and for the interrupted rebase that is
    the whole difference between finishing and parking. A rebase REPLAYS the
    branch: the commit the pull request still carries is on no local history
    afterwards, so git counts the branch as behind its own publication --
    ahead by the replay and the base it moved onto, behind by the object it
    replaced. Read off those counts, the canonical pre-push recovery is
    indistinguishable from a remote somebody else pushed to, and the tick that
    only ever needed to reissue its push parks instead. The remote standing
    EXACTLY on the anchor this rebase pinned before git ran is what says
    nothing landed in between, and it is the same fact the force-with-lease
    behind the retry is pinned to.

    The counts still answer for every remote neither SHA accounts for, which
    is the case they were always about: a publication that moved out of band
    is behind as well as ahead, and a pair of zeros over two heads that
    disagree is a reading that did not happen.
    """
    completed = snapshot._complete_recovery_snapshot(
        context, recovery_snapshot,
    )
    if completed is None:
        return True
    carried = transfers._carried_by(context.state, completed.local_head)
    if completed.local_head and completed.local_head == completed.remote_head:
        return _finish_published_recovery(context, completed, carried)
    if completed.remote_head == context.pending_pre_rebase_sha:
        return _retry_recovery_push(context, completed, carried)
    return _route_a_moved_remote(context, completed, carried)


def _route_a_moved_remote(
    context: _AutoRebaseRecoveryContext,
    completed: _AutoRebaseRecoverySnapshot,
    carried: transfers._Handoff,
) -> bool:
    """Route a remote neither SHA this recovery holds accounts for.

    Reached once the pull request is proved to be standing on neither the
    rewrite this branch carries nor the anchor the rebase pinned before git
    ran, so whatever is on it arrived from somewhere else. The counts are what
    is left to tell those apart, and they answer the question they were always
    about: a pair of zeros over two heads that disagree is a reading that did
    not happen, a remote with commits of its own is one a force-push would
    drop, and a strictly-ahead branch is a lease this recovery may still try
    -- the push is pinned to the anchor, so a remote that is not on it refuses
    the request rather than being overwritten.
    """
    if completed.ahead == 0 and completed.behind == 0:
        return outcomes._reject_unknown_recovery_comparison(context, completed)
    if completed.behind > 0:
        return outcomes._park_diverged_recovery(context, completed)
    return _retry_recovery_push(context, completed, carried)


def _recover_pending_auto_base_rebase(
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Finalize a clean auto-base-rebase interrupted by a prior crash.

    The pinned pre-rebase SHA distinguishes an unchanged worktree, an
    already-published rewrite, an ahead-only rewrite that still needs a
    push, and a branch that diverged through an out-of-band update. Returns
    False only when HEAD still equals the anchor and the normal rebase flow
    should continue on the same tick.
    """
    bound_fields = _RECOVERY_SIGNATURE.bind(*args, **kwargs)
    bound_fields.apply_defaults()
    context = _AutoRebaseRecoveryContext(**bound_fields.arguments)
    return _recover_pending_auto_base_rebase_context(context)


_recover_pending_auto_base_rebase.__signature__ = _RECOVERY_SIGNATURE
