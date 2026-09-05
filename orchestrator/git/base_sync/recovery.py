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
    _PendingRewrite,
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

_UNPROVEN_LANDING = (
    "the pull request and the checkout agree on `{published}` and nothing "
    "this attempt recorded names it, so the publication in front of this tick "
    "is not one it can show it made"
)

_REFUSED_PERMIT = (
    "the permit that would license the settlement refused this tick -- the "
    "pull request, the stage, the checkout, the lease, or the two "
    "contributions no longer agree with the permission on the comment, and "
    "the orchestrator log names which"
)

_UNROTATED = (
    "the push went out and the verdict did not move with it, so the "
    "permission granted for `{published}` is still outstanding"
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
    inspect.Parameter(
        "pending_rewrite",
        inspect.Parameter.KEYWORD_ONLY,
        default=_PendingRewrite(),
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

    Both roads are asked one thing first: whether the commit the pull request
    and the checkout agree on is the replay this attempt recorded making. They
    agreeing proves only that they agree -- somebody who moved the branch and
    the remote together leaves exactly this shape -- and finishing there drops
    the anchor that is the only thing bringing this recovery back.

    Every other handoff is then asked whether the pinned comment ACCOUNTS for
    the rewrite the pull request carries, and only an accounted one is
    finished.
    An issue carrying no verdict always is, which is the ordinary interrupted
    rebase and the whole of what this road used to be. One whose transfer
    settled, or whose replay the ordinary cumulative gate published, is
    accounted for by the receipt that write left. Anything else -- a record
    this build cannot read, a receipt nobody wrote, a debt nothing paid --
    parks with the anchor still pinned, because finishing there would drop the
    one thing that brings this recovery back and leave the next tick to
    measure an adjudicated change as a fresh candidate.
    """
    landed = recovery_snapshot.local_head or ""
    if not context.pending_rewrite.names(landed):
        return outcomes._park_unfinished_recovery(
            context, recovery_snapshot,
            _UNPROVEN_LANDING.format(published=landed or "an unreadable head"),
        )
    if carried == transfers._Handoff.OUTSTANDING:
        return _settles_the_landed_rewrite(context, recovery_snapshot)
    unaccounted = transfers._unaccounted_publication(
        context.state, landed, context.pending_pre_rebase_sha, carried,
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

    Asked of the PERMIT before the gate, and refused rather than measured.
    The gate's own fallback for a permit that declines is the ordinary
    cumulative reading -- which is the right answer for a rebase deciding
    whether to publish, and the wrong one here twice over. A count under the
    ceiling would report this call as a landed publication and let the route
    finish with the permission still outstanding and the verdict still on the
    commit a human ruled on; a count over it would route an adjudicated change
    into a second adjudication with the pull request already carrying the
    work. There is nothing to measure on this road at all: the remote has the
    commit, and the only question is whether the permission may be spent.

    Asked again on the far side, because a permit that granted before the
    gate is not proof the settlement happened: the terms are re-read inside,
    and anything that moved in between leaves the push landed and the verdict
    where it was. The rotation itself is the answer, so it is read off the
    record rather than assumed.

    A refused push is the one thing that can still go wrong, and it is a
    remote that moved between this tick's fetch and the request. Nothing is
    reset for it: the checkout is standing on the commit the pull request was
    carrying a moment ago, and putting it back on the anchor would take the
    branch off work the remote has. The anchor stays pinned, the issue parks,
    and the next recovery classifies the remote afresh.
    """
    landed = recovery_snapshot.local_head or ""
    if not transfers._permits_the_settlement(context, landed):
        return outcomes._park_unfinished_recovery(
            context, recovery_snapshot, _REFUSED_PERMIT,
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
            candidate=landed,
        ),
    )
    if published.held:
        context.gh.write_pinned_state(context.issue, context.state)
        return True
    if not published.landed:
        return outcomes._park_unfinished_recovery(
            context, recovery_snapshot, _REFUSED_NO_OP,
        )
    if not transfers._rotated_onto(context.state, landed):
        return outcomes._park_unfinished_recovery(
            context, recovery_snapshot, _UNROTATED.format(published=landed),
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

    Both are answered by exact SHAs rather than by the ahead/behind counts,
    and for the interrupted rebase that is the whole difference between
    finishing and parking. A rebase REPLAYS the branch: the commit the pull
    request still carries is on no local history afterwards, so git counts the
    branch as behind its own publication -- ahead by the replay and the base
    it moved onto, behind by the object it replaced. Read off those counts,
    the canonical pre-push recovery is indistinguishable from a remote
    somebody else pushed to, and the tick that only ever needed to reissue its
    push parks instead. What tells them apart is the pair of heads the attempt
    itself recorded: the anchor the remote must still be standing on, and the
    replay the checkout must still be.

    A remote the RECORD says has already carried this replay is refused
    before anything is pushed at it. The receipt behind a landed push, and the
    settled transfer that rides the same write, are both claims that the pull
    request had this commit -- so a pull request that no longer does was rolled
    back by somebody, and the anchor the retry would lease against is exactly
    the head they rolled it back to. The lease would be satisfied and the
    rollback overwritten, which is the one thing a lease exists to stop.

    A record nobody can vouch for is refused before either road that would
    publish anything. Left to the ordinary gate, a damaged transfer group over
    an adjudicated commit is measured afresh, sent past the same ceiling, and
    routed into a second adjudication with a pull request already open over
    the work -- so the branch goes back onto the anchor and a human is asked.

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
    return _route_an_unpublished_head(context, completed, carried)


def _route_an_unpublished_head(
    context: _AutoRebaseRecoveryContext,
    completed: _AutoRebaseRecoverySnapshot,
    carried: transfers._Handoff,
) -> bool:
    """Route a checkout the pull request is not standing on.

    Three refusals before the one road that pushes, in the order the evidence
    for them costs nothing to read. A remote the record says already carried
    this replay has been rolled back by somebody, and the anchor a retry would
    lease against is the head they rolled it back to. A record nobody can
    vouch for would reach the ordinary cumulative gate and send an adjudicated
    change into a second adjudication. And a checkout this attempt cannot show
    it produced is not one to force-push under a lease every rebuilt worktree
    and every operator reset satisfies just as well.

    What is left is the retry the anchor exists for, and -- for a remote
    neither pinned head accounts for -- the counts, which answer the question
    they were always about.
    """
    if transfers._rolled_back_publication(context, completed, carried):
        return outcomes._park_rolled_back_recovery(context, completed)
    if carried == transfers._Handoff.UNVOUCHED:
        return outcomes._park_unvouched_recovery(context, completed)
    if _is_this_attempts_rewrite(context, completed):
        return _retry_recovery_push(context, completed, carried)
    return _route_a_moved_remote(context, completed, carried)


def _is_this_attempts_rewrite(
    context: _AutoRebaseRecoveryContext,
    completed: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Whether the checkout is the replay this attempt made, over its anchor.

    Both halves, and neither is enough alone. The REMOTE has to be standing
    exactly on the anchor the rebase pinned before git ran, which is what says
    no push of this attempt's landed and what the force-with-lease behind the
    retry is pinned to. And the CHECKOUT has to be the head that attempt
    recorded as its own replay, which is the only thing that says the
    divergence in front of this tick is the rebase's work rather than a
    worktree somebody rebuilt, an operator's reset, or a branch pointed
    somewhere else -- every one of which satisfies the same lease and would
    take the candidate off the pull request.

    Empty provenance answers no. That is the window between git returning and
    the write that records the replay, and there the recovery falls back to
    the counts it always used: a strictly-ahead branch is a fast-forward the
    anchor lease loses nothing to, and a divergent one parks.
    """
    if completed.remote_head != context.pending_pre_rebase_sha:
        return False
    return context.pending_rewrite.names(completed.local_head)


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
