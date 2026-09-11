# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The size question a committed candidate answers before it is published.

The seam the whole late gate hangs off. Every clean committed developer
outcome -- a run that finished, one the timeout killed after it had committed,
and one recovered from a branch a crash stranded -- reaches publication
through one place, so measuring here is what makes the three of them one
contract: whatever is about to be pushed is measured first, and an oversized
candidate is held rather than published.

Held, not discarded. Nothing is pushed, no pull request is opened, and the
commit stays exactly where the developer left it; what changes is the label,
which hands the issue to the late coordinator under `workflow:decomposing`.
That coordinator owns everything past this point -- the hold, the
adjudication, and what a `single` or a `split` verdict earns -- and it
reconciles the very record this gate froze.

The order of the steps is the failure contract. The candidate is proved to be
a commit this host holds, the base is frozen from what the REMOTE says the
branch is at, and both are persisted with the `measuring` boundary BEFORE a
single line is counted: a tick that dies over the count comes back to the pair
this one froze rather than to a candidate re-derived from a branch that has
moved since. A reading that could not be taken is never a small candidate --
it is a typed failure on both sinks, and the retry a trusted bare
`/orchestrator continue` drives re-measures that recorded pair without
re-running the developer who already finished. Most of those failures park at
once. The two that name the TRANSPORT rather than the work -- a base the
remote would not answer for, and one a fetch did not bring back -- clear
themselves often enough to be worth a bounded number of quiet tries first: the
miss goes on the record and nothing else happens, no human is told, and only
the pair that has lost the last of them is parked. The failure is reported
even where no pair was ever frozen: the identity is minted for the record
rather than the refusal going unsaid, and deliberately not persisted, since a
pinned cycle with no candidate under it reconciles nothing and would read as a
live cycle to the guard that ends one when the issue is closed.

What a candidate an approval let through still owes is a PUSH, and the commit
it owes it for is recorded before the write that drops the generation naming
it. The checkout is proved to be ON that commit before any later tick spawns
or republishes -- the object alone outlives the branch -- so a checkout the
work never reached parks for the worktree rather than publishing what it
carries or paying for a second developer over it.

What the record already NAMES is what a later tick reconciles, and the current
head is never a substitute for it. A recorded candidate is proved before
anything else -- a host that cannot peel that object is one the work was not
made on, and it parks rather than measuring or publishing whatever the branch
points at there -- and a recorded base is retried by asking for that exact
object rather than by reading the remote again, which would answer with
wherever the branch has moved to and measure a different pair under the same
generation. Only once both commits are proved present does a head that differs
mean what it usually means -- and only on a disposition with a run behind it:
a developer resumed on a human's guidance who committed again, which is a
fresh candidate. A reconciliation has no such run, so a head that moved
between the proof its caller took and the one taken here is a checkout
something moved mid-tick, and it is refused rather than measured or pushed.

Five candidates skip the measurement, and none is a bypass. Three of them are
commits this workflow has already DECIDED about, and they are recognized the
same way, by naming one commit and only it -- work committed on top of any of
them is measured as the fresh candidate it is. One is the exact commit an
adjudication accepted, which the exemption names. One is the commit an
approval still owes a push: a crash between the write that approves a
candidate and the push it licenses brings the same commit back here with its
generation already retired, and re-deciding it there would re-measure a
settled question against a base that has moved since -- routing work a human
may already have adjudicated back into adjudication. One approval is not that,
and it defers: a commit an approval names only because a rewrite TRANSFER let
it past was never read here at all, so the permit that licensed it is re-asked
over the record the grant left rather than answered on the object id. One is
the commit this
stage already PUSHED, which is that window one step further on: past the push
a pull request carries the work and only the relabel is owed, so a reading
that came back oversized there would hold nothing back and route a published
branch to adjudication. The fourth is a NEW candidate while `DECOMPOSE` is
off -- the switch decides whether new work enters the gate and decides nothing
about work already in it, about a reconciliation answering a reading the gate
itself recorded, or about a commit it has already approved or published. In it
means a generation naming THIS commit: one naming another is a record a
resumed developer's fresh commit has moved past, so the fresh commit is the
new work the switch publishes untouched and the superseded record is retired
rather than left over a commit nothing will push.

The fifth is the only one no record names in advance: a REWRITE of the exact
commit an authorized settlement accepted. A squash on approval and the refresh's own
clean base rebase each replace that commit with an object carrying the
identical contribution, and the one-commit rule that makes the exemption safe
is what stops it answering for the replacement -- so the same change would be
measured past the same ceiling and adjudicated again, with a pull request
already open over the work. It is the only candidate here
that EARNS its way past the reading rather than being recognized, and
`late_transfer` is the whole of what it is earned on: a permit granted only
over a semantic record that PROVES itself -- re-fingerprinted over its own
recorded pair, so the base it names is checked rather than stepped around --
beside a publication confirmed unmoved, a clean checkout standing on the
rewritten commit, a leased head that peels to a commit this host holds, an
issue re-read and found unchanged -- open, unpaused, and still on the stage the
rewrite was entered from -- no unreadable authorization already standing for
the exempt commit, and a rewritten contribution that fingerprints to the same
digest. Refused, nothing moves and the candidate is measured like
any other. Granted, one write carries the PERMISSION and the debt the push
it licenses is still owed -- the exemption itself does not move here, since a
verdict rotated onto a commit no remote has is one a failed push would strand.
What moves it is the write that receipts the landed push, one seam further on,
and until then a granted permission simply stands.

This owner is the order those questions are asked in and nothing else. What a
tick is ABOUT is `late_records`, the pair it measures over is `late_freeze`,
the reading itself is `late_reading`, what a recovery proves first is
`late_evidence`, what a receipt has to prove before it vouches for anything is
`late_delivery`, what a rewrite of an accepted commit may carry with it is
`late_transfer`, what an answer earns is `late_verdict`, and what a refusal
costs is `late_parks`.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
from orchestrator.git.measurement import (
    models as _measurement,
)
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    state as _late_state,
)
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.implementing import (
    late_consent as _consent,
    late_delivery as _delivery,
    late_freeze as _freeze,
    late_parks as _parks,
    late_reading as _reading,
    late_records as _records,
    late_transfer as _transfer,
    late_verdict as _verdict_owner,
    models as _models,
)

log = logging.getLogger("orchestrator.workflow")

# Why a candidate skips the measurement, spelled as the log line reads it.
# What a checkout standing somewhere other than the commit its caller named
# is reported and parked as.
_MOVED_OFF_THE_CALLER = (
    "the commit handed to it was `{named}` and its checkout stands on "
    "`{head}`"
)


_MOVED_OFF_THE_CALLER_PARK = (
    "{mentions} this stage read `{named}` as the commit it was about to "
    "publish, and the checkout it would publish from stands on `{head}`. "
    "Something committed over the worktree between the two readings, so the "
    "two are not one candidate -- measured and pushed as it stands, this "
    "issue would put `{head}` on the pull request while recording `{named}` "
    "as what it published. Nothing was pushed and nothing was recorded. "
    "Reconcile the worktree with what landed and the next tick reads it "
    "afresh."
)


_ADJUDICATED = "was adjudicated as one change"

_APPROVED = "is the commit this gate approved and has still to push"

_PUBLISHED = "is the commit this stage has already pushed"

_SWITCHED_OFF = "is new work the size gate is switched off for"

def _holds_committed_work(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue: Issue,
    state: PinnedState,
    work: _models._AgentWork,
) -> _records._GateVerdict:
    """Whether the size gate keeps this committed candidate unpublished.

    `held` is the whole of what this tick did with the candidate: it is either
    parked on a reading nobody could take or handed to the late coordinator,
    and on both the caller publishes nothing. Not held means the candidate is
    this repository's to publish exactly as it always was -- small, already
    adjudicated, or never measured because the switch is off -- and the SHA
    beside it is the commit that earned that, which is what the push is then
    named against.

    A record already carrying a measurement for the commit in hand is acted on
    rather than re-taken, once it is proved to be a whole one this host can
    still show. The threshold on it is the one that generation was frozen
    under, so a setting retuned between two ticks cannot re-judge a candidate
    mid-flight, and a crash between the count and the label costs a label
    write rather than another reading of the same diff.
    """
    recovering = isinstance(work, _models._RecoveredWork)
    return _holds_candidate(_records._Gate(
        gh=gh, spec=spec, issue=issue, state=state, worktree=work.worktree,
        reconciling=recovering,
        # Every recovery here answers a reading this gate itself recorded --
        # a late park a human replied to, an approval whose push never went
        # out, a frozen pair a crash stranded -- so the switch has nothing
        # left to say about any of them.
        answering=recovering,
        # And each of them proved the checkout on that reading's own commit
        # before handing it over, so the head this owner reads is held to it:
        # the worktree is writable in between, and a commit landing there is
        # a candidate no reading covers.
        candidate=work.candidate_sha if recovering else "",
    ))


def _holds_candidate(gate: _records._Gate) -> _records._GateVerdict:
    """The size question one committed candidate answers, whatever asked it.

    The order of the questions rather than the seam that reaches them, which
    is what lets the gate stand in front of the initial publication and in
    front of a push onto a pull request the remote already carries without
    either seam re-deriving the contract. Every difference between the two is
    in the subject it is handed: the publication the call was entered on, the
    checkout, and whether a developer ran.

    A park a previous reading left is deliberately NOT cleared on the way in.
    Entering the gate is not answering the question it was taken for, and the
    two owners past here that do answer it retire it themselves -- so a tick
    that re-read the pair and missed again leaves the park exactly as it
    found it, rather than durably unparking an issue whose reading still has
    not happened.
    """
    recorded = _records._entered(
        gate, _late_state.read_late_generation(gate.state),
    )
    candidate = _freeze._candidate_commit(gate, recorded)
    if candidate is None:
        return _verdict_owner._unmeasured_verdict(gate, recorded)
    if not candidate.is_frozen:
        return _unnameable(gate, recorded, candidate)
    if _moved_off_the_caller(gate, recorded, candidate.sha):
        return _records._HELD
    return _decided(gate, recorded, candidate.sha)


def _decided(
    gate: _records._Gate, recorded: LateGeneration, candidate_sha: str,
) -> _records._GateVerdict:
    """What one proved candidate earns, once the checkout is its caller's.

    The two answers past the proof, in the order the record decides them: a
    commit this workflow has already ruled on publishes without a reading, and
    everything else is measured -- the recorded count acted on where there is
    one, a fresh pair frozen and counted where there is not.

    Between them sits the one commit that is neither yet: a REWRITE of a
    change a human already ruled on. It is asked second because every question
    ahead of it is a record read off the pinned comment and this one spends
    two fingerprints and a fresh owner read, and because a commit the record
    already calls decided has nothing left to earn. Refused, the candidate
    falls through to the measurement exactly as it always did.

    The delivery proof is taken ONCE, at the top and for every candidate,
    because the road past the measurement that rests on it -- a commit this
    stage's own receipt names -- may not take a second reading of its own: a
    second answer is a second chance to disagree with a decision already made.
    It costs no request unless the receipt names the candidate in hand, and
    none at all on a call that froze a publication of its own.

    The permit's answer is kept APART from the other three rather than folded
    into the one reason, because the two license different things. All four
    say the candidate may publish without a reading; only the permit says a
    human's verdict may move onto it once that publication lands. A refusal
    that fell through to the measurement, and a count the ceiling then let
    through, publish the same commit under an answer nothing vouched for --
    so the write past the push is handed this commit and not the record, and
    a permit that refused rotates nothing however readable the permission
    beside it still is.
    """
    if _consent._awaits_an_operator(gate, candidate_sha):
        # An issue already behind the authorization park, over an exemption
        # naming this very commit, is the one place a record saying "decided"
        # may not be believed: what that park doubts is the exemption itself,
        # an adjudicator's ruling with no operator behind it, so reading it
        # here would publish the bypass the park exists to withhold. It is
        # asked ahead of every other question for that reason, and it is the
        # only entry into the policy -- nothing in this build takes the park,
        # so the answer is False on every ordinary tick and every candidate
        # takes the road below, the one a park over a commit nothing exempts
        # takes too.
        return _held_or_published(
            candidate_sha,
            _consent._holds_until_authorized(gate, recorded, candidate_sha),
        )
    delivered = _delivery._delivered_before_the_relabel(gate, candidate_sha)
    decided = _needs_no_measuring(gate, recorded, candidate_sha, delivered)
    permitted = decided or _transfer._carried_over(gate, candidate_sha)
    if permitted:
        log.info(
            "issue=#%d candidate %s %s; publishing it without a reading",
            gate.issue.number, candidate_sha, permitted,
        )
        return _verdict_owner._unmeasured_verdict(
            gate, recorded, _records._GateVerdict(
                held=True,
                candidate_sha=candidate_sha,
                permitted_sha="" if decided else candidate_sha,
                delivered_pr=delivered,
            ),
        )
    answered = (
        recorded.candidate_sha == candidate_sha
        and recorded.additions is not None
    )
    held = (
        _reading._reconciled_measurement(gate, recorded) if answered
        else _reading._freshly_measured(gate, recorded, candidate_sha)
    )
    return _held_or_published(candidate_sha, held)


def _held_or_published(
    candidate_sha: str, held: bool,
) -> _records._GateVerdict:
    """One reading's answer as the verdict its caller publishes or holds by.

    The SHA travels with the go-ahead because the caller's next step is a
    push, and a push that named nothing would publish whatever the checkout
    points at when it runs.
    """
    if held:
        return _records._HELD
    return _records._GateVerdict(held=False, candidate_sha=candidate_sha)


def _approved_on_a_reading(
    gate: _records._Gate, candidate_sha: str,
) -> bool:
    """Whether this commit's debt rests on a decision this gate already made.

    An approval is the gate's own answer brought back by a crash, which is
    what makes skipping the reading for it a repeat rather than a bypass. One
    exception, and it is the only approval that was never a reading at all: a
    commit an approval names because a rewrite TRANSFER let it past. What
    licensed that push is a permit, granted on terms -- a pull request, a
    stage, a record, two fingerprints -- that can each stop being true between
    the grant and the tick that comes back to pay the debt.

    So a debt an OUTSTANDING permission stands beside defers to the permit,
    which `late_transfer` re-asks in full over the record the grant left. That
    is asked of the permission rather than of the commit it names, because the
    two go down in one write for one commit: an approval beside an outstanding
    permission is either the one it licensed or evidence the record disagrees
    with itself, and a hand-edited target would otherwise make the permit
    invisible and leave the approval looking ordinary.

    Refused, the ordinary cumulative gate measures the rewrite like any other
    candidate: an oversized change nothing may publish unmeasured is exactly
    what an unvalidatable permission leaves behind.
    """
    if _parks._approved_commit(gate.state) != candidate_sha:
        return False
    return not _transfer._licensed_by_a_permit(gate.state)


def _moved_off_the_caller(
    gate: _records._Gate, recorded: LateGeneration, candidate_sha: str,
) -> bool:
    """Refuse a checkout that is not the commit its caller named.

    The caller read a head for itself -- the commit its docs pass made, the
    one its squash collapsed to, the resolution it just committed -- and this
    owner proves the checkout's head again, because everything past here is a
    claim about one object id and a caller's word is not a proof. Between the
    two reads the worktree is writable, so a commit landing in that window is
    a DIFFERENT candidate: measured here, pushed here, and recorded here,
    while the caller goes on to stamp the id it read as the one it published.

    So the two are made one decision. Asked before anything is persisted or
    pushed, because that is the whole point: a refusal after the freeze leaves
    a record about the wrong commit, and one after the push leaves the wrong
    commit on the pull request.

    A recovery names one for the same reason a run does, and proves it for a
    sharper one: no developer ran, so the reading that licensed the recovery
    is about a commit a previous tick recorded, and a head that moved between
    that proof and this one is not a fresh candidate to measure in its place.
    It is a commit an operator's authorization does not cover, published on
    its own count while the record names another.

    Silent where the caller named nothing -- a bounce over a checkout it did
    not just write -- and where the two agree, which is every ordinary tick.
    """
    if not gate.candidate or gate.candidate == candidate_sha:
        return False
    log.error(
        "issue=#%d was handed %s to publish and its checkout stands on %s; "
        "refusing to measure a candidate its caller never read",
        gate.issue.number, gate.candidate, candidate_sha,
    )
    return _parks._parked(
        gate, _records._named(gate, recorded, candidate_sha),
        _MOVED_OFF_THE_CALLER.format(
            named=gate.candidate, head=candidate_sha,
        ),
        _MOVED_OFF_THE_CALLER_PARK.format(
            mentions=config.HITL_MENTIONS,
            named=gate.candidate,
            head=candidate_sha,
        ),
    )


def _unnameable(
    gate: _records._Gate,
    recorded: LateGeneration,
    candidate: _measurement.FrozenCommit,
) -> _records._GateVerdict:
    """Park a candidate nobody could freeze, under the id it did name.

    A reading can fail with an id in hand, and the commonest one does: a
    revision that resolved and would not peel -- an object a prune took, or
    work made on a host this one is not -- comes back carrying the id it
    resolved to. That id is the only record of which commit the attempt was
    about, so it goes down with the park rather than being reported and
    dropped. Recorded, the retry asks for that exact object, the pre-tick base
    refresh holds the branch still around it, and the reconciliation ahead of
    the next spawn proves it before anything runs. Reported and dropped, none
    of those three has anything to act on: the branch is rebased under the
    park and the next reading proves whatever the checkout points at by then,
    which is how base or somebody else's work is measured and published as
    this issue's implementation.

    A revision that would not resolve at all names nothing, and there the park
    itself is the record: no pair was frozen, so nothing may be reconciled
    against one and the retry says so rather than taking a first reading of a
    head it cannot tie to this issue.
    """
    named = _records._named(gate, recorded, candidate.sha)
    if named.candidate_sha and named.candidate_sha != recorded.candidate_sha:
        _parks._persisted(gate, named)
    _parks._unmeasured(gate, named, candidate.failure, candidate.detail)
    return _records._HELD


def _already_decided(
    gate: _records._Gate, candidate_sha: str, delivered: int,
) -> str:
    """Why the RECORD says this commit needs no reading, or "" if it does not.

    Three records say a commit was already DECIDED about, and they say it the
    same way: by naming one commit and only it, so anything committed on top
    of any of them is work nobody decided about and is measured as the fresh
    candidate it is.

    The exemption is a verdict a human's adjudication reached, and it outlives
    the publication because the gate would otherwise measure the same
    candidate past the same ceiling forever. The approval is this gate's own
    -- with the one exception a permit granted it, which defers to that permit
    rather than answering on the object id alone -- and it lives only until
    the push it licenses lands: the write that
    approves a candidate drops the generation naming it, so a crash before the
    push brings the same commit back here with nothing left to say it was
    already settled. Measuring it again is not a second opinion -- the base
    has moved since, so it is a different question -- and answering it can
    route work a human already adjudicated straight back into adjudication.

    The publication record is that same window read from its far end, and the
    one that matters most because the effects are already out, and it is the
    one asked against the REMOTE rather than off the record alone: a receipt
    naming a commit the pull request has since moved off records a
    publication that is over, and work the remote no longer carries is work
    this gate has not decided about. past the push
    the branch is on the remote and a pull request carries it, while the label
    still says implementing until the relabel lands. A relabel that failed
    leaves the next tick reading a published branch as work nobody has ruled
    on, and an oversized answer there would route it to adjudication with
    nothing left to hold back -- the one outcome this gate exists to prevent.
    So the commit is recognized rather than re-read, the pull request that
    already carries it is reused, and the relabel is finished.

    What the receipt is held to is `late_delivery`'s, and it differs by seam
    rather than being skipped on either. A call taken PAST a publication froze
    the head the pull request is standing on, and the two are read together
    here. One taken before it froze nothing, so the same question goes to the
    remote -- the pull request the record names, open, on the branch this seam
    would push, standing on this exact commit -- because a note that is never
    cleared is not on its own evidence that anything still carries the work.
    """
    if _exemption.is_exempt(gate.state, candidate_sha):
        return _ADJUDICATED
    if _approved_on_a_reading(gate, candidate_sha):
        return _APPROVED
    if _parks._published_commit(gate.state) != candidate_sha:
        return ""
    frozen = gate.entry.published_sha if gate.entry else ""
    vouched = (
        _delivery._receipt_answers_alone(gate, candidate_sha, delivered)
        and (not frozen or frozen == candidate_sha)
    )
    return _PUBLISHED if vouched else ""


def _needs_no_measuring(
    gate: _records._Gate,
    recorded: LateGeneration,
    candidate_sha: str,
    delivered: int,
) -> str:
    """Why this commit publishes without a reading, or "" where it needs one.

    The records that say a commit was already decided about come first, and
    `_already_decided` beside this owns all of them.

    The switch is the last answer and is asked last, here rather than at the
    door, for the one state the door could not settle. An approval keeps
    the switch from bypassing, because a commit this gate decided has to be
    published under the id it decided about -- and that is a claim about ONE
    commit, which nothing can check until the head is proved. Past that proof
    and not it, the approval describes work this branch has moved past: the
    candidate in hand is new work, and new work is exactly what the switch
    keeps out of the gate. A record already in the gate, and a call answering
    a reading the gate itself took, are neither -- and the second is asked as
    `answering` rather than as the wider "no developer ran", which a rebase, a
    resolution, and a recovery push each set over work this gate has never
    seen.

    "A record already in the gate" is a record about THIS commit, which is the
    same claim by one commit and only it the three above are recognized by. A
    generation naming some OTHER candidate is one a resumed developer's fresh
    commit has moved past, and the fresh commit is new work: measured where
    the switch is on, published untouched where it is off, and in both cases
    the superseded record is retired rather than left over a commit nothing
    will publish. Read as "in the gate" instead, an install with the switch
    off measures exactly the work it turned the gate off for.
    """
    decided = _already_decided(gate, candidate_sha, delivered)
    if decided:
        return decided
    already_read = (
        recorded.candidate_sha == candidate_sha or gate.answering
    )
    if config.DECOMPOSE or already_read:
        return ""
    return _SWITCHED_OFF
