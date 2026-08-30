# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The push a squash-on-approval makes over the branch it just rewrote.

The tenth seam that publishes onto a pull request the remote already carries,
and it goes through the whole gate like the other nine. What it publishes is a
NEW object: a squash collapses the approved commits into one commit that did
not exist when any earlier push was measured, so that commit is the candidate
-- proved, frozen against the base the remote names now, counted, and either
pushed or held. Measuring the head it replaces instead would gate one commit
and publish another.

The count it earns is ordinarily the count the last gated push already
answered, because the tree is the same tree. Ordinarily is not always: the
BASE moves, and a base that advanced since that push changes what this branch
adds to it. That is the reading this seam exists to take -- it is the last
push before a human is asked to merge, so a pull request that has crossed the
ceiling since anyone looked would otherwise reach the merge button
unadjudicated.

A candidate the RECORD names ends the tick without a rollback. Past the
ceiling the gate has moved the issue to `workflow:decomposing` and a settled
`single` verdict publishes the squash from the branch; short of a count the
pair is one the reconciliation ahead of the next handler owes a reading, and
that reading can only be taken in the checkout it was frozen on. Either way
restoring the pre-squash head would leave a record naming a commit this branch
no longer has -- adjudicated over a commit nobody has, or refused by every
later tick as a candidate that moved. The same holds for a push that landed
and for a checkout something committed over: in each the squash is somebody's
and a reset is the destructive step.

A REFUSED one is the opposite and is told apart from all of them, because the
squash there is a local commit nobody measured, nobody published, and nothing
recorded -- an entry that could not prove itself deliberately persists none.
Left on the branch it is the ONE commit a retry finds, which takes the
nothing-to-squash road and reports success without measuring or pushing
anything -- so the approved work reaches the merge button neither counted nor
on the remote. `_rewrite_stands` is what the caller asks before it decides.

The entry is asked TWICE, and the first time is not redundant. A pull request
nothing could read, one a human closed mid-review, a dirty tree, or a head
that moved out from under the reading are all answerable while the branch is
still intact, and asking them there is what keeps a doomed publication from
costing a rewrite and a rollback to learn about. Closing a pull request does
not move its branch, so that first reading is also the only thing standing
between a `--force-with-lease` and a publication nobody can merge.
"""
from __future__ import annotations

import logging

from orchestrator import config
from orchestrator.git.measurement import commits as _measurement_commits
from orchestrator.workflow.late_split import state as _late_state
from orchestrator.workflow.stages.implementing import (
    late_freeze as _freeze,
    late_overflow as _overflow,
    late_parks as _parks,
    late_push as _push,
    late_records as _records,
)

log = logging.getLogger("orchestrator.workflow")


# The revision a checkout's own head is named by.
_HEAD = "HEAD"


# How a squash can fail to be the thing this owner publishes. Each is spelled
# as the park comment reads it, because what an operator has to reconcile
# differs by which side of the push it was noticed on.
_MOVED_CHECKOUT = (
    "the squash made `{squashed}` and the checkout stands on `{head}`"
)


_MOVED_SQUASH_PARK = (
    "{mentions} the reviewer approved this pull request and the orchestrator "
    "squashed its commits, but the checkout it squashed in is not the one the "
    "squash left behind: {refusal}. Something committed over the worktree "
    "while the publication was being made, so nothing has been handed on -- "
    "and the branch is left exactly as it was found rather than reset, since "
    "whatever moved it made a commit nobody here can account for. Reconcile "
    "the worktree with what landed and the next tick squashes afresh."
)


def _switched_off(gate: _records._Gate) -> bool:
    """Whether the switch keeps this squash out of the gate entirely.

    A squash is NEW work by the switch's own definition: the commit it
    publishes is one it makes itself, out of commits a reviewer approved. So
    an install with `DECOMPOSE=off` reads no pull request and parks over none.

    It is the gate's own question, asked HERE rather than left to the reading
    inside the call, because this seam reaches that reading twice and the
    first of the two is the pull-request read the switch is supposed to save.
    The subject it is asked over answers `answering` False, which is what a
    squash is: no developer ran on the tick, and nothing on the record asked
    for this commit to be read.

    A record already in the gate, and a commit an approval still owes a push,
    are work the switch has nothing left to say about either way.
    """
    return _freeze._outside_the_gate(
        gate, _late_state.read_late_generation(gate.state),
    )


def _entered_rewrite(
    gate: _records._Gate, expected: str,
) -> _records._PublicationEntry:
    """The publication a squash may rewrite, or the reason it may not.

    Asked before the reset that destroys the branch locally, so a pull request
    nothing can be published onto costs the caller a refusal rather than a
    rewrite it then has to roll back.

    `expected` is the pre-squash head this stage read and will lease its
    force-push against, checked against the head the publication is standing
    on exactly as every other caller's is: the two are one fact, and a squash
    taken over a branch somebody pushed to would rewrite their work away.

    Where the switch keeps this squash out of the gate, nothing is read and
    nothing can refuse: what comes back names only the head the caller
    established, which is what the force-push behind it is pinned to. An
    install with `DECOMPOSE=off` therefore squashes and pushes under the lease
    this stage read for itself, and under no other claim about the remote.
    """
    if _switched_off(gate):
        return _records._PublicationEntry(published_sha=expected)
    entry = _overflow._frozen_entry(
        gate, _records._Entered(head=expected, reconciling=True),
    )
    if not entry.is_frozen:
        log.error(
            "issue=#%d cannot squash onto the pull request it already has "
            "(%s); leaving the approved commits on the branch",
            gate.issue.number, entry.refusal,
        )
    return entry


def _publishes_rewrite(
    gate: _records._Gate,
    branch: str,
    entry: _records._PublicationEntry,
    squashed: str,
) -> _push._PushedCandidate:
    """Measure the squashed commit, then publish what it earned.

    The one call every gated push goes through, handed the head this stage
    established: the entry re-freezes over it, the checkout is proved to be
    standing on the commit the squash just made, the diff from the frozen base
    to it is counted, and only a candidate at or under the ceiling is pushed
    -- named against that commit and pinned to the frozen head.

    `reconciling` is what this call is: no developer ran on this tick, so a
    checkout that is not on the squashed commit is something that moved rather
    than a run's fresh output, and it is refused rather than measured as new
    work. It says nothing about the switch, which is asked against the
    narrower `answering` -- and a squash never is one: the commit it publishes
    is one it makes itself, out of commits a reviewer approved.

    `entry` is what the caller froze before it rewrote anything. It is not
    handed to the gate -- the entry inside the call is the one the record
    carries -- but the head it names is, so both readings are pinned to the
    same fact and the second cannot silently freeze a publication the first
    would have refused.

    `squashed` is asked twice, and the second is the binding one. The gate
    proves HEAD for itself and a first generation has no record to prove it
    against, so handed a checkout something moved between the squash and the
    freeze it would measure and publish the replacement as if it were the
    squash. Naming the commit closes that: the gate refuses a checkout it was
    not handed, before anything is persisted or pushed. The reading before the
    call is the cheap half -- it refuses without spending the pull-request
    read the entry costs.
    """
    if not _standing_on_the_squash(gate, squashed):
        return _push._PushedCandidate(held=True)
    return _push._publishes(
        gate, branch,
        _records._Entered(
            head=entry.published_sha,
            reconciling=True,
            # The commit the squash made, so the gate measures and publishes
            # THAT rather than whatever the checkout became between the two
            # reads. Bound here, a move in that window is refused before
            # anything is persisted or pushed rather than noticed after.
            candidate=squashed,
        ),
    )


def _rewrite_stands(gate: _records._Gate, squashed: str) -> bool:
    """Whether a HELD squash must be left on the branch it rewrote.

    A hold is not one state. Three of its shapes leave the squashed commit
    somebody's, and in each the reset the caller would otherwise take is the
    destructive step:

    * the push LANDED and only the handoff was held -- the receipt names the
      squash, so the remote carries it and a reset would take the branch off
      a commit the pull request has;
    * the RECORD names it -- any live generation whose candidate is the
      squash, not merely an oversized one. Past the ceiling the adjudication
      owns it and a settled `single` verdict publishes it from this branch;
      short of a count the pair is one the reconciliation ahead of the next
      handler owes a reading, and that reading can only be taken in the
      checkout it was frozen on -- put back, the record names a commit the
      branch no longer has, and every later tick refuses it as a candidate
      that moved instead of measuring it again;
    * the checkout is not the squash at all -- something committed over it --
      and a reset would destroy work nobody here can account for.

    Everything else is a reading that refused before it froze anything: a pull
    request a human closed mid-rewrite, a head somebody moved under it, an
    approval nothing could pin. Those persist no record -- an entry that could
    not prove itself deliberately writes none -- so nothing names the squash,
    and leaving it on the branch is what makes the retry find ONE commit, take
    the nothing-to-squash road, and report success without measuring or
    pushing anything -- so the approved work reaches the merge button neither
    counted nor on the remote. Put back, the retry finds the commits it was
    approved with and squashes, measures, and publishes them afresh.

    The two questions are one rule read from its ends: the branch may go back
    only where nothing durable is left pointing at what is on it.

    The checkout is proved again here rather than taken from the reading
    before the push, and the two guard different steps: that one decides
    whether to PUBLISH, and a whole gated push stands between it and the
    reset this one decides.
    """
    if _parks._published_commit(gate.state) == squashed:
        return True
    if _late_state.read_late_generation(gate.state).candidate_sha == squashed:
        return True
    proved = _measurement_commits._prove_candidate_commit(gate.worktree, _HEAD)
    return not (proved.is_frozen and proved.sha == squashed)


def _standing_on_the_squash(gate: _records._Gate, squashed: str) -> bool:
    """Whether the checkout is still the commit the squash just made.

    Proved rather than read: a revision this host cannot peel is not a head
    that matches anything. A checkout standing somewhere else is not rolled
    back to the pre-squash head either -- whatever moved it committed
    something, and a reset would destroy work nobody here can account for. It
    parks with the branch exactly as it was found.
    """
    proved = _measurement_commits._prove_candidate_commit(gate.worktree, _HEAD)
    if proved.is_frozen and proved.sha == squashed:
        return True
    return _refuses_the_squash(
        gate,
        _MOVED_CHECKOUT.format(
            squashed=squashed, head=proved.sha or "an unreadable head",
        ),
    )


def _refuses_the_squash(gate: _records._Gate, refusal: str) -> bool:
    """Park a squash whose checkout is not the commit it was handed, and stop.

    Reported and parked the way every other reading this gate could not take
    is, so an operator sees one shape for "the checkout is not what this was
    about" whichever side of the push it was noticed on. The flags are left in
    memory for the caller that ran this to persist, exactly as the gate's own
    parks are.
    """
    log.error(
        "issue=#%d cannot publish the squash it made (%s); refusing to hand a "
        "checkout nobody squashed to the pull request",
        gate.issue.number, refusal,
    )
    _parks._parked(
        gate, _records._reportable(gate, _late_state.read_late_generation(
            gate.state,
        )),
        refusal,
        _MOVED_SQUASH_PARK.format(
            mentions=config.HITL_MENTIONS, refusal=refusal,
        ),
    )
    return False


def _forgets_the_rollback(gate: _records._Gate, restored: str) -> None:
    """Drop a debt the rollback above just threw the commit away for.

    The gate approves the squashed commit before it is pushed and records it
    as one still owed a publication. A push that is then refused rolls the
    branch back to the pre-squash head, so that commit is not on this branch
    any more and only the reflog still has it.

    Left standing, it is a debt nothing can pay and everything trips over: the
    reconciliation ahead of every handler finds an approval whose commit the
    checkout is not on and stops the tick for a publication that is never
    coming, poll after poll. An approval whose commit was abandoned is
    superseded, which has always been one of the three things that drops one
    -- so the owner doing the abandoning is the one that drops it.

    Made durable HERE rather than left for the caller's own write, because
    what it answers for has already happened: the branch is back on the
    pre-squash head, and a process that died before that write would come back
    to exactly the debt this exists to prevent.
    """
    if _parks._approved_commit(gate.state) == restored:
        return
    _parks._forget_approval(gate.state)
    gate.gh.write_pinned_state(gate.issue, gate.state)
