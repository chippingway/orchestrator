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
That coordinator owns everything past this point -- the plan-PR hold, the
adjudication, and what a `single` or a `split` verdict earns -- and it
reconciles the very record this gate froze.

The order of the steps is the failure contract. The candidate is proved to be
a commit this host holds, the base is frozen from what the REMOTE says the
branch is at, and both are persisted with the `measuring` boundary BEFORE a
single line is counted: a tick that dies over the count comes back to the pair
this one froze rather than to a candidate re-derived from a branch that has
moved since. A reading that could not be taken is never a small candidate --
it is a typed failure on both sinks and an explicit park, and the retry a
trusted bare `/orchestrator continue` drives re-measures that recorded pair
without re-running the developer who already finished. The failure is reported
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

Four candidates skip the measurement, and none is a bypass. Three of them are
commits this workflow has already DECIDED about, and they are recognized the
same way, by naming one commit and only it -- work committed on top of any of
them is measured as the fresh candidate it is. One is the exact commit an
adjudication accepted, which the exemption names. One is the commit an
approval still owes a push: a crash between the write that approves a
candidate and the push it licenses brings the same commit back here with its
generation already retired, and re-deciding it there would re-measure a
settled question against a base that has moved since -- routing work a human
may already have adjudicated back into adjudication. One is the commit this
stage already PUSHED, which is that window one step further on: past the push
a pull request carries the work and only the relabel is owed, so a reading
that came back oversized there would hold nothing back and route a published
branch to adjudication. The fourth is a NEW candidate while `DECOMPOSE` is
off -- the switch decides whether new work enters the gate and decides nothing
about work already in it, about a reconciliation answering a reading the gate
itself recorded, or about a commit it has already approved or published.

This owner is the order those questions are asked in and nothing else. What a
tick is ABOUT is `late_records`, the pair it measures over is `late_freeze`,
what a recovery proves first is `late_evidence`, what an answer earns is
`late_verdict`, and what a refusal costs is `late_parks`.
"""
from __future__ import annotations

import logging
from dataclasses import replace

from github.Issue import Issue

from orchestrator import config
from orchestrator.git.measurement import (
    additions as _additions,
    models as _measurement,
)
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import (
    events as _events,
    exemption as _exemption,
    state as _late_state,
)
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.implementing import (
    late_freeze as _freeze,
    late_parks as _parks,
    late_verdict as _verdict_owner,
    models as _models,
)
from orchestrator.workflow.stages.implementing import (
    late_records as _records,
)

log = logging.getLogger("orchestrator.workflow")

# Why a candidate skips the measurement, spelled as the log line reads it.
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
    gate = _records._Gate(
        gh=gh, spec=spec, issue=issue, state=state, worktree=work.worktree,
        reconciling=isinstance(work, _models._RecoveredWork),
    )
    _parks._retire_spent_park(state)
    recorded = _late_state.read_late_generation(state)
    candidate = _freeze._candidate_commit(gate, recorded)
    if candidate is None:
        return _unmeasured_verdict(gate, recorded)
    if not candidate.is_frozen:
        return _unnameable(gate, recorded, candidate)
    unmeasured = _needs_no_measuring(gate, recorded, candidate.sha)
    if unmeasured:
        log.info(
            "issue=#%d candidate %s %s; publishing it without a reading",
            issue.number, candidate.sha, unmeasured,
        )
        return _unmeasured_verdict(gate, recorded, candidate.sha)
    if _freeze._already_measured(recorded, candidate.sha):
        return _verdict(_reconciled_measurement(gate, recorded), candidate.sha)
    return _verdict(
        _freshly_measured(gate, recorded, candidate.sha), candidate.sha,
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
    _parks._unmeasured(gate, named, candidate.failure)
    return _records._HELD


def _needs_no_measuring(
    gate: _records._Gate, recorded: LateGeneration, candidate_sha: str,
) -> str:
    """Why this commit publishes without a reading, or "" where it needs one.

    Three records say a commit was already DECIDED about, and they say it the
    same way: by naming one commit and only it, so anything committed on top
    of any of them is work nobody decided about and is measured as the fresh
    candidate it is.

    The exemption is a verdict a human's adjudication reached, and it outlives
    the publication because the gate would otherwise measure the same
    candidate past the same ceiling forever. The approval is this gate's own,
    and it lives only until the push it licenses lands: the write that
    approves a candidate drops the generation naming it, so a crash before the
    push brings the same commit back here with nothing left to say it was
    already settled. Measuring it again is not a second opinion -- the base
    has moved since, so it is a different question -- and answering it can
    route work a human already adjudicated straight back into adjudication.

    The publication record is that same window read from its far end, and the
    one that matters most because the effects are already out: past the push
    the branch is on the remote and a pull request carries it, while the label
    still says implementing until the relabel lands. A relabel that failed
    leaves the next tick reading a published branch as work nobody has ruled
    on, and an oversized answer there would route it to adjudication with
    nothing left to hold back -- the one outcome this gate exists to prevent.
    So the commit is recognized rather than re-read, the pull request that
    already carries it is reused, and the relabel is finished.

    The switch is the last answer and is asked last, here rather than at the
    door, for the one state the door could not settle. An approval keeps
    the switch from bypassing, because a commit this gate decided has to be
    published under the id it decided about -- and that is a claim about ONE
    commit, which nothing can check until the head is proved. Past that proof
    and not it, the approval describes work this branch has moved past: the
    candidate in hand is new work, and new work is exactly what the switch
    keeps out of the gate. A record already in the gate, and a reconciliation
    answering a reading the gate itself took, are neither.
    """
    if _exemption.is_exempt(gate.state, candidate_sha):
        return _ADJUDICATED
    if _parks._approved_commit(gate.state) == candidate_sha:
        return _APPROVED
    if _parks._published_commit(gate.state) == candidate_sha:
        return _PUBLISHED
    if config.DECOMPOSE or recorded.candidate_sha or gate.reconciling:
        return ""
    return _SWITCHED_OFF


def _unmeasured_verdict(
    gate: _records._Gate, recorded: LateGeneration, candidate_sha: str = "",
) -> _records._GateVerdict:
    """Publish a candidate this gate did not measure -- unless a close beat it.

    The three ways past the measurement, and they share the step that is easy
    to miss: a record may still be standing. The switch being off does not
    retire what an earlier tick froze, and an exemption names one commit
    rather than ending the generation that granted it -- so the retirement
    that has to land before the push runs here too, and with it the close
    protocol it carries. Held is the answer where a close ended the cycle: an
    issue nobody wants gets no branch, no pull request, and no relabel.

    An approval naming some OTHER commit is the same problem one field over,
    and it is dropped for the same reason: the debt it records is for a commit
    this publication is going past, and a record left over work nothing will
    push freezes the branch and parks every later tick asking for it back.
    """
    _verdict_owner._supersedes_approval(gate, candidate_sha)
    if _verdict_owner._superseded(gate, recorded):
        return _records._HELD
    return _records._GateVerdict(held=False, candidate_sha=candidate_sha)


def _verdict(held: bool, candidate_sha: str) -> _records._GateVerdict:
    """Name the commit a candidate that may publish is published under."""
    if held:
        return _records._HELD
    return _records._GateVerdict(held=False, candidate_sha=candidate_sha)


def _reconciled_measurement(gate: _records._Gate, recorded: LateGeneration) -> bool:
    """Act on a measurement this issue already took, or park on what is left.

    A count on the record is not on its own a measurement anything may act on.
    It is one END of a reading whose other fields say what it MEANS: without a
    base there is no pair it was taken over, without a threshold there is no
    ceiling to compare it to -- and `is_oversized` answers False on a missing
    one, which is the shape of a damaged record publishing as a small
    candidate -- and without a boundary there is nothing saying which step
    wrote it. Without a whole identity naming THIS issue there is nothing to
    join it to afterwards, or it is somebody else's reading entirely. A record
    short of any of them is repaired by a human or measured again, never read
    as an answer.

    The recorded base is proved present for the same reason it is on the way
    in: a host that cannot show the object the count was taken against cannot
    show the diff a verdict is defended by either, and acting on the number
    while the evidence behind it is missing is the substitution this whole
    contract refuses.
    """
    if _freeze._damaged_record(gate, recorded):
        return True
    if _freeze._refrozen_base(gate, recorded) is None:
        return True
    return _verdict_owner._settled(gate, recorded)


def _freshly_measured(
    gate: _records._Gate, recorded: LateGeneration, candidate_sha: str,
) -> bool:
    """Freeze the pair, count between it, and act on what came back."""
    frozen = _freeze._frozen_pair(gate, recorded, candidate_sha)
    if frozen is None:
        return True
    counted = _additions._count_added_lines(
        gate.worktree, frozen.base_sha, frozen.candidate_sha,
    )
    if not counted.is_measured:
        return _parks._unmeasured(gate, frozen, counted.failure)
    measured = replace(frozen, additions=counted.additions)
    _parks._emit(
        gate, measured,
        _events.LateEvent(family=_events.LateEventFamily.MEASUREMENT),
    )
    return _verdict_owner._settled(gate, measured)
