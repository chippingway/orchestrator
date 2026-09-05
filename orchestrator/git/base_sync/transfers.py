# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a rebase replaced, and how far the transfer of its exemption got.

A clean base rebase is a REWRITE of whatever the branch was standing on, and
on an issue whose exemption names that commit the replay is the one thing that
would punish it: the exemption names one commit and only it, so the object the
replay produced is measured past the same ceiling and the change a human
already adjudicated goes back into adjudication with a pull request open over
the work. What stops that is a permit, and a permit is granted on EVIDENCE --
the pair the adjudication recorded, the pair the replay produced, and the
publication the push is made against. This owner assembles that evidence, and
it sits beside the publisher rather than inside it because the tick that made
the rewrite is not the only one that needs it.

The refresh pins its recovery anchor before git runs, rebases, records the
permission, pushes, and receipts that push -- five durable moments with four
windows between them, and a process can die in any of them. What the next tick
comes back to is a checkout on the replay and a pinned comment that got as far
as it got, so before a recovery may finish anything it has to know which of
those it is looking at. That is the second half of this owner, and the answers
are closed:

* `NOTHING` -- no verdict is being carried here at all. The ordinary
  interrupted rebase, which the ordinary recovery finishes.
* `UNRECORDED` -- the replay is on the branch and no permission was ever
  written. The grant was still ahead of the crash, so the record cannot supply
  the evidence and the recovery assembles it exactly as the interrupted tick
  would have.
* `OUTSTANDING` -- a permission stands for this very head and the push it
  licensed has not been receipted. The record IS the evidence, re-asked in
  full rather than believed, and the receipt is what this recovery still owes.
* `SETTLED` -- the receipt landed and the exemption is already on the head.
  Nothing is left to move, and a recovery that moved anything here would be
  making a second claim about a transfer one write already finished.
* `UNVOUCHED` -- a group is standing that this build cannot read whole, or one
  claiming a commit that is not the head in hand. Nothing is assembled and
  nothing is settled: the ordinary cumulative gate measures the replay, which
  is the answer a permission nobody can check has to get.

Only `UNRECORDED` is handed fresh evidence, and that asymmetry is the safety
rule. A grant REPLACES the whole authorization group rather than adding beside
it, so a recovery that assembled a claim of its own over a group already
standing would repair a record nobody checked, under the authority of the very
transfer it is in the middle of deciding.

The last question here is the one a road with nothing left to publish has to
ask: whether the rewrite the pull request already carries is one this comment
can ACCOUNT for. Finishing that road clears the recovery anchor, and the
anchor is the only thing that brings the tick back -- so an exemption still on
the old commit, a debt nothing paid, or a receipt nobody wrote may not be
walked past, however right the remote looks.
"""
from __future__ import annotations

from enum import StrEnum

from orchestrator.git.base_sync.models import (
    _AutoRebaseContext,
    _AutoRebaseRecoveryContext,
)
from orchestrator.git.base_sync.state import log
from orchestrator.git.measurement import commits as measurement_commits
from orchestrator.github.pinned_state import PinnedState


class _Handoff(StrEnum):
    """How far the exemption an interrupted rebase was carrying got."""

    NOTHING = "nothing"
    UNRECORDED = "unrecorded"
    OUTSTANDING = "outstanding"
    SETTLED = "settled"
    UNVOUCHED = "unvouched"


# The two handoffs a landed rewrite can be ACCOUNTED for under: the transfer
# finished, or none was ever granted and the ordinary gate published it. Both
# leave a receipt naming the commit, which is what the accounting is read off.
_ACCOUNTABLE = frozenset((_Handoff.SETTLED, _Handoff.UNRECORDED))


# Why a rewrite the pull request already carries is one the pinned comment
# cannot account for. Each is worded for the operator who has to reconcile it,
# because what they all end in is a park nobody but a human clears.
_UNREADABLE_CLAIM = (
    "a transfer record this build cannot read whole is standing over the "
    "commit this issue exempts"
)

_UNSETTLED_CLAIM = "the transfer standing here is `{handoff}` rather than over"

_UNRECEIPTED = (
    "nothing on the pinned comment records `{published}` as published, so "
    "whether the verdict this rebase was carrying ever moved cannot be said"
)

_UNPAID = (
    "a push is still recorded as owed for `{owed}`, so the write that should "
    "have settled this publication did not land whole"
)


def _rewritten_by_the_rebase(
    context: _AutoRebaseContext | _AutoRebaseRecoveryContext,
    before_sha: str,
    after_sha: str,
):
    """What this rebase replaced, as the evidence a transfer is granted on.

    Assembled here because this is the one place both halves of the claim are
    in hand at once. The pair the contribution came FROM is the one the
    adjudication already recorded -- the commit a human ruled on and the base
    it was measured over -- and it is the only pair a verdict may be moved off
    and the only one a later reader re-derives the equality from. The pair it
    went TO is this rebase's own: the head the replay left, which moves with
    the next commit, and the base the branch now sits over, which is what the
    remote says its base branch is at.

    Nothing is decided here. Whether the two pairs are one contribution is the
    gate's question, asked over fingerprints taken from the objects
    themselves, and every other term this hands over is re-asked there against
    the publication the gate froze for itself.

    The base is frozen from what the REMOTE says the branch is at rather than
    read off the local ref the rebase named, and that is the whole of what
    keeps the pair honest. `refs/remotes/<remote>/<base>` lives in the object
    store the issue's agent writes to and any worktree sharing it can repoint
    -- after this tick's fetch, at that. A replay onto a ref carrying work the
    remote does not have fingerprints as the little that sits on top of it,
    while the pull request against the real base carries that work and this
    change together, and the permit would wave the pair through unmeasured. Read
    from the remote, the forged base is simply a different contribution and the
    ordinary cumulative gate measures it -- which costs one authenticated read
    on the rare tick an exempt issue is rebased.

    Empty where either half cannot be shown, and that is a claim withheld
    rather than a refusal reported. A comment with no semantic record -- an
    issue that never earned an exemption, one written before the record
    existed, one whose fingerprint could not be taken -- has no accepted pair
    to name, and a base the remote would not name, or one this host does not
    hold even after a fetch, is no commit to read a contribution over. In both
    the rebase is measured exactly as it always was.

    The pre-rebase anchor goes down as the LEASE rather than as the commit
    that was replaced, and the two are deliberately kept apart. It is the head
    the pull request is standing on and the head the force-push behind this is
    pinned to; that it is also the commit the exemption names is what the
    equality of the two contributions proves, and not something this owner may
    assert by spelling one field from the other.
    """
    # Lazy import: the exemption record and the rewrite vocabulary sit in the
    # workflow layer above this package, so binding them at module load would
    # make every git-side import pay for the stage tree they pull in.
    from orchestrator.workflow.late_split import (
        exemption as _exemption,
        rewrites as _rewrites,
    )
    identity = _exemption.read_semantic_identity(context.state)
    if identity is None:
        return None
    replayed_onto = measurement_commits._freeze_base_commit(
        context.spec, context.worktree,
    )
    if not replayed_onto.is_frozen:
        return None
    return _rewrites.LateRewrite(
        kind=_rewrites.LateRewriteKind.AUTO_CLEAN_REBASE,
        from_sha=identity.candidate_sha,
        from_base_sha=identity.base_sha,
        to_sha=after_sha,
        to_base_sha=replayed_onto.sha,
        pr_number=context.pr_number,
        source_stage=context.label,
        lease=before_sha,
    )


def _carried_by(state: PinnedState, local_head: str) -> _Handoff:
    """How far the transfer this interrupted rebase was making got.

    Read off the pinned comment alone, and asked before any of the recovery's
    own effects, because it is what decides which of them the tick owes: a
    permission still outstanding is a receipt this recovery has to land, one
    already spent is a route it only has to finish, and a rewrite the grant
    never reached is evidence it has to assemble for itself.

    Asked of the PERMISSION rather than of the commit the exemption names, for
    the reason every other reader of this record is: the grant writes the
    permission and the debt in one write for one commit, so a group whose
    target somebody edited would otherwise be invisible here and the recovery
    would carry on as though no transfer had ever been in flight.

    Costs no git and no request. Every answer is a field this issue already
    carries, which is what lets the ordinary recovery -- the overwhelming
    majority, on issues that never earned an exemption -- pay nothing for a
    question that is not about it.
    """
    # Lazy for the reason every upward reach in this package is: the record
    # sits in the workflow layer above it.
    from orchestrator.workflow.late_split import exemption as _exemption
    standing = _standing_permission(state, local_head)
    if standing is not None:
        return standing
    if _exemption.read_semantic_identity(state) is None:
        return _Handoff.NOTHING
    return _Handoff.UNRECORDED


def _standing_permission(
    state: PinnedState, local_head: str,
) -> _Handoff | None:
    """What a permission already on the comment says about this head, or None.

    None only where the comment carries no claim this recovery has to answer
    for: no group at all, and a group whose transfer is over and whose commit
    is not the one in hand -- which is an exemption an earlier rewrite moved
    with a fresh rebase standing on top of it, so the evidence for THIS replay
    is the recovery's to assemble like any other.

    Everything else is a claim. A group this build cannot read back whole, and
    one still outstanding for some other commit, are both refused rather than
    replaced: the group is the only account there is of how the exemption came
    to name what it names, and a recovery that overwrote one would be
    repairing evidence nobody checked.
    """
    # Lazy for the reason every upward reach in this package is: the record
    # sits in the workflow layer above it.
    from orchestrator.workflow.late_split import rewrites as _rewrites
    if not _rewrites.carries_rewrite_authorization(state):
        return None
    authorization = _rewrites.read_rewrite_authorization(state)
    if authorization is None:
        return _Handoff.UNVOUCHED
    settled = authorization.phase == _rewrites.LateRewritePhase.PUBLISHED
    if authorization.rewrite.to_sha == local_head:
        return _Handoff.SETTLED if settled else _Handoff.OUTSTANDING
    return None if settled else _Handoff.UNVOUCHED


def _reconstructed(
    context: _AutoRebaseRecoveryContext,
    local_head: str,
    carried: _Handoff,
):
    """The evidence a recovery hands the gate where the grant never landed.

    The one window the record cannot answer for itself. An interrupted tick
    rebased and died before the write that would have said what the replay
    replaced, so the reissued push reaches the gate with nothing on the
    comment naming a rewrite -- and the ordinary cumulative gate measures a
    change a human already ruled on past the same ceiling, with a pull request
    open over the work.

    Assembled from exactly the readings the interrupted tick would have taken:
    the pair the adjudication recorded, the head the checkout is standing on,
    the base the REMOTE names, and the pinned anchor as the lease. Nothing is
    inherited from the dead tick, because nothing of it survived -- and
    nothing has to be, since every term is re-asked by the permit against the
    publication the gate freezes for itself.

    None for every other handoff, each for its own reason: a permission still
    outstanding IS the evidence and is re-asked over the terms the grant was
    taken on, a spent one describes a transfer that is over, one nobody can
    vouch for may not be replaced by a claim this owner made up, and an issue
    carrying no verdict has nothing to carry.
    """
    if carried != _Handoff.UNRECORDED:
        return None
    rewrite = _rewritten_by_the_rebase(
        context, context.pending_pre_rebase_sha, local_head,
    )
    if rewrite is not None:
        log.info(
            "issue=#%d auto-rebase recovery: the interrupted tick left %s on "
            "the branch and no permission for it; re-deriving what the replay "
            "of %s contributes so the gate rules on the transfer it would have",
            context.issue.number, local_head[:8], rewrite.from_sha[:8],
        )
    return rewrite


def _unaccounted_publication(
    state: PinnedState, local_head: str, carried: _Handoff,
) -> str:
    """Why a rewrite the pull request already carries is unexplained, or "".

    Asked of the road that has nothing left to publish and only a route to
    finish, and it is what decides whether finishing is safe. That route
    clears the recovery anchor, resets the review round, and hands the issue
    to the reviewer -- which on an issue carrying no verdict is exactly right
    and costs nothing, since there is no transfer for a missing record to
    strand.

    On an issue that WAS carrying one it is the opposite. The anchor is the
    only thing that brings this recovery back, so clearing it over an
    exemption still on the old commit, a debt nothing paid, or a receipt
    nobody wrote leaves the next tick to measure the rewrite as a fresh
    candidate -- past the same ceiling, and back into adjudication with the
    pull request already carrying the work. So those states park with the
    anchor left pinned instead, and a human settles what is on the comment.

    Two handoffs can be accounted for, and both by the same record: a transfer
    that FINISHED wrote the receipt in the same statement as the rotation, and
    a rewrite no permit ever licensed was published by the ordinary cumulative
    gate, which wrote one too. So the receipt naming this commit is what says
    the publication is explained, and the debt beside it is asked as well --
    the two go down together, so an approval still standing over a receipted
    commit is a write that did not land whole.

    A group nobody can read is refused outright: it is the only account there
    is of how the exemption came to name what it names, and a route finished
    over it would be acting on evidence nothing checked.
    """
    if carried == _Handoff.NOTHING:
        return ""
    if carried not in _ACCOUNTABLE:
        if carried == _Handoff.UNVOUCHED:
            return _UNREADABLE_CLAIM
        return _UNSETTLED_CLAIM.format(handoff=carried)
    # Lazy for the reason every upward reach in this package is: the receipt
    # and the debt sit in the workflow layer above it.
    from orchestrator.workflow.stages.implementing import late_parks
    if late_parks._published_commit(state) != local_head:
        return _UNRECEIPTED.format(published=local_head)
    owed = late_parks._approved_commit(state)
    return _UNPAID.format(owed=owed) if owed else ""
