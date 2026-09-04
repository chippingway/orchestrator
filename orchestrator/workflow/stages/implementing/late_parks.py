# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a refusal costs, and the two sinks every one of them reaches.

One park shape for every reading the size gate could not take, because the
recovery is the same for all of them: the issue is handed back with the step
that failed named, the typed failure goes to the audit and analytics streams,
and a trusted bare `/orchestrator continue` re-reads rather than re-running
anything. The writes those steps ride out on are here too, since a park and a
persisted record are the two durable things this domain does.

What reaches those streams is the same three things the thread is told, and
for the same reason: the family says a reading did not happen, the member
beside it says which step stopped, and the line the step wrote says why. An
operator holding only the stream would otherwise have `measurement_failed` for
a remote that was throttling, a checkout that is gone, and a diff nothing can
pin, and no way to count one apart from the others.

Two of the steps a reading stops at get a bounded number of tries before that
happens, and they are the two that name the transport rather than the work: a
remote that would not answer for the base branch, and a fetch that did not
bring the base object back. Those clear themselves -- a network, a token, a
host that was down -- so the first few are counted on the record and nothing
else is done at all, and only a pair that has lost the last of them is worth a
human's attention. Every other member still parks on its first miss, because
re-reading a candidate this host does not hold or a diff nothing can pin buys
exactly the same answer.

Past ANY of those parks the pair is still read on every poll -- the
post-publication reconciliation takes that reading ahead of every handler --
and what those readings owe the thread is one sentence per thing there is to
say rather than one per poll. So the member a notice named is recorded, and it
is recorded by the roads that announce and by no other: a quiet miss tells
nobody anything, and a step written down by one would be a notice the guard
thinks was made. A reading stopping at the recorded member repeats a sentence
already on the issue and is held silently -- reported to the log and to both
sinks, said to no one. One stopping somewhere else is a different next move
for whoever is holding the issue, and nothing else would ever tell them, so it
is announced once and takes the recorded member's place.

What each member means to that person is spelled out here too. The vocabulary
is written for the code that branches on it, and a park that named only the
member would leave a human to work out for themselves whether they are looking
at a remote, a token, a checkout, or something planted in one.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from types import MappingProxyType

from github.Issue import Issue

from orchestrator import config
from orchestrator.git.measurement.models import MeasurementFailure
from orchestrator.github.client import GitHubClient
from orchestrator.github.comments import filter_trusted
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import (
    guards as _guards,
    messages as _messages,
)
from orchestrator.workflow.late_split import (
    events as _events,
    formats as _formats,
    payloads as _payloads,
    state as _late_state,
    telemetry as _telemetry,
)
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.implementing import (
    late_records as _records,
    state as _state,
)

log = logging.getLogger("orchestrator.workflow")

PARK_MEASUREMENT_FAILED = "late_measurement_failed"

# The steps a lost reading is retried quietly for, and the only two. Both name
# the transport between this host and the base -- a remote that would not
# answer for the branch, and a fetch that did not bring the object back -- and
# a transport fault is the one thing in this vocabulary that clears itself
# while nobody is watching. Every other member names something a second
# reading cannot change: a candidate this host does not hold, a diff nothing
# here can pin. Re-reading those buys the same answer, so they park on the
# first miss and ask a human for the one thing that would change it.
_TRANSPORT_STEPS = frozenset((
    MeasurementFailure.BASE_UNREADABLE,
    MeasurementFailure.BASE_ABSENT,
))

_UNMEASURED_PARK = (
    "{mentions} this issue's committed implementation could not be measured "
    "({failure}), so it has not been published: a candidate whose size is "
    "unknown is not a small one, and pushing it would publish an "
    "implementation nobody adjudicated. Nothing was discarded -- the commit "
    "is still in the worktree, and the exact pair this attempt froze is "
    "recorded. Fix what the reading needs, then reply `/orchestrator "
    "continue` and the same commit is measured again without re-running the "
    "developer."
)

# The same refusal where the work already has a pull request. It is worded
# apart because both halves of the recovery differ: nothing is waiting to be
# published for the first time, and a bare continue on these stages resumes
# the developer rather than re-reading a pair -- so the notice says what is
# true here and asks for nothing that would spend an agent.
_UNMEASURED_PUBLISHED_PARK = (
    "{mentions} what this issue's pull request would come to could not be "
    "measured ({failure}), so the commit in the worktree has not been pushed "
    "to it: a candidate whose cumulative size is unknown is not a small one, "
    "and pushing it would grow a pull request nobody adjudicated. Nothing was "
    "discarded -- the commit is still in the worktree, the pull request still "
    "stands where it did, and the exact pair this attempt froze is recorded. "
    "Fix what the reading needs and the same pair is measured again."
)

# What each step means to the operator who has to clear it, one line apiece.
# The member is what code branches on and what the record and the streams
# carry, and on a thread it says nothing: `candidate_absent` names a host to
# bring a commit to and `diff_unpinnable` names a checkout to clean, and the
# difference between them is the whole of somebody's next move. The lines are
# here rather than beside the vocabulary because they are addressed to the
# human on this issue -- what was refused, and what would change it -- rather
# than to the step that stopped.
_FAILURE_LINES = MappingProxyType({
    MeasurementFailure.BASE_UNREADABLE: (
        "The `git ls-remote` this reading takes against the base branch never "
        "came back with a commit, so there was no base to diff against: a "
        "remote that could not be reached or was throttling the request, or a "
        "token that has expired or cannot see this repository. Three retries "
        "have already been taken quietly, one per tick, and the same pair "
        "goes on being re-read on every tick after this notice -- so a "
        "transport that comes back settles this with no reply at all. The "
        "invocation that failed is logged under `orchestrator.git_plumbing`."
    ),
    MeasurementFailure.BASE_ABSENT: (
        "The remote named the base commit and a fetch did not bring that "
        "object to this host, so there was nothing here to take the diff "
        "against: a base branch rewritten under this clone, an object a prune "
        "took, or a fetch that could not finish. It is retried on the same "
        "quiet bound as `base_unreadable` and re-read on every tick after "
        "this notice, and the fetch is logged under "
        "`orchestrator.git_plumbing`."
    ),
    MeasurementFailure.CANDIDATE_UNREADABLE: (
        "The commit this issue is about does not resolve in the worktree on "
        "this host -- a checkout that was rebuilt, reset, or reaped out from "
        "under the record. Restore the checkout that holds it, or commit the "
        "work again; another reading of the same worktree answers the same "
        "way."
    ),
    MeasurementFailure.CANDIDATE_ABSENT: (
        "The revision resolved to an object id this host cannot read as a "
        "commit -- work made on a host this one is not, or an object a prune "
        "took. The commit has to be here before any reading of it can be "
        "taken."
    ),
    MeasurementFailure.DIFF_UNPINNABLE: (
        "The checkout carries configuration that would decide what counts as "
        "text -- a repository diff driver, or a planted `info/attributes` "
        "file -- and no override this reading takes reaches either, so a "
        "count taken under it could be made to read as a small candidate. "
        "Clear it in the worktree before the pair is measured again."
    ),
    MeasurementFailure.DIFF_FAILED: (
        "`git diff` over the two frozen commits exited non-zero, so no count "
        "came back at all. The invocation and what it wrote are logged under "
        "`orchestrator.git_plumbing`."
    ),
    MeasurementFailure.DIFF_UNREADABLE: (
        "`git diff --numstat` answered with a record this build cannot count, "
        "so no number could be taken from it. The invocation is logged under "
        "`orchestrator.git_plumbing`."
    ),
})

# What the step said for itself, where it said anything. Free text a human
# reads rather than anything to branch on, and scrubbed of the credential by
# the transport long before it reaches here.
_REPORTED_DETAIL = "The step reported: {detail}"


def _described(failure, detail: str) -> str:
    """The line an operator acts on, and what the step said for itself.

    The member alone is a contract term: it tells the reading what to do and
    tells the person holding the issue nothing about what to fix. So the
    notice carries the sentence written for them, and the transport's own line
    after it where there is one -- by the time a human reads this the process
    that saw that stderr is minutes and a tick gone, and nothing else kept it.

    Empty for a member no line covers, which is what keeps the notice's own
    sentences the contract: a park says what was refused whether or not this
    table has caught up with the vocabulary.
    """
    described = _FAILURE_LINES.get(failure, "")
    if not detail:
        return described
    reported = _REPORTED_DETAIL.format(detail=detail)
    return f"{described} {reported}" if described else reported


def _parked(
    gate: _records._Gate, generation: LateGeneration, failure, message: str,
    detail: str = "",
) -> bool:
    """Record the typed failure on both sinks, then hand the issue back.

    Every reading that did not happen is reported, which is why the generation
    reaching here is one a caller has already made reportable: a candidate the
    gate could not even name has no record of its own yet, and the identity
    minted for it is what lets the failure be joined to the cycle a later
    freeze writes under the same number.

    `failure` is whatever the caller stopped at, and the roads in do not agree
    about what that is: the ones a reading refused name a member, while the
    ones a RECORD refused -- a pinned comment too damaged to act on, a debt no
    push can pay -- name the repair in their own words, because the whole
    point of those parks is telling a human which part to fix. The record
    keeps the member where there is one and says nothing where there is not,
    so a step nobody reached is never reported as one that was.
    """
    log.error(
        "issue=#%d committed work could not be measured (%s); parking rather "
        "than publishing an unadjudicated candidate",
        gate.issue.number, failure,
    )
    _emit(gate, generation, _events.measurement_failure_event(failure, detail))
    _guards._park_awaiting_human(
        gate.gh, gate.issue, gate.state, message,
        reason=PARK_MEASUREMENT_FAILED,
    )
    gate.state.set(_state._PARK_REASON, PARK_MEASUREMENT_FAILED)
    return True


def _unmeasured(
    gate: _records._Gate, generation: LateGeneration, failure,
    detail: str = "",
) -> bool:
    """Park a candidate nobody could measure, loudly and with its reason.

    Never "small". What a failed `git` invocation writes to stdout is nothing,
    which is what a candidate that changes nothing writes too, so publishing
    on that reading is precisely how an unadjudicated implementation goes out.

    The step is named twice over: as the member every other surface carries,
    and as the line an operator acts on. A notice that named only the member
    would hand somebody a term this vocabulary owns and leave them to guess
    which of a remote, a token, a checkout, or a planted attribute file the
    next move is about.

    Loudly ONCE per cause, and this is the one place that can be decided:
    every reading refused for a typed step reaches a human through here, and
    the pair behind a park is re-read on every poll after it. Said again each
    time, a base nobody can fetch or a diff nothing can pin would mention the
    same people once a poll, for as long as it takes them to fix it -- which
    is a notification channel nobody can answer faster by reading twice. So a
    refusal a standing park has already announced is held instead: reported to
    the log and to both sinks like every other reading that did not happen,
    and said to no one. A refusal that stops SOMEWHERE ELSE is not a repeat --
    it is a different next move for whoever is holding the issue, and nothing
    else would ever tell them -- so it is said, and takes the announced
    member's place.
    """
    if _repeats_a_notice(gate, generation, failure):
        return _held_quietly(gate, generation, failure, detail)
    _records_the_notice(gate, generation, failure)
    unmeasured = _UNMEASURED_PARK
    if gate.entry is not None:
        unmeasured = _UNMEASURED_PUBLISHED_PARK
    refused = unmeasured.format(
        mentions=config.HITL_MENTIONS, failure=failure,
    )
    described = _described(failure, detail)
    if described:
        refused = f"{refused}\n\n{described}"
    return _parked(
        gate, _announced(generation, failure), failure, refused, detail,
    )


def _repeats_a_notice(
    gate: _records._Gate, generation: LateGeneration, failure,
) -> bool:
    """Whether the thread has already been told THIS about THIS pair.

    Both halves are required and each rules out a different way of swallowing
    a notice nobody has made. The park has to be one somebody is still waiting
    behind and taken over this very pair, which `_stands_over` answers; and
    the step has to be the one that park's own notice named, which only a road
    that announced something ever wrote down. A record that says nothing is a
    pair nobody has been told about, so it is told.
    """
    if not _stands_over(gate, generation):
        return False
    recorded = _late_state.read_late_generation(gate.state)
    return recorded.measurement_failure == failure


def _held_quietly(
    gate: _records._Gate, generation: LateGeneration, failure,
    detail: str = "",
) -> bool:
    """Report a refusal a human has already been sent, and tell them nothing.

    Silent to the THREAD and to nothing else. The typed failure goes to both
    sinks here as it does on every other reading that did not happen: the
    published road deliberately re-reads this pair on every poll, so the
    stream is the only place those readings exist at all, and a hold that
    reported none of them would make a pair nobody can measure look
    indistinguishable from one nobody is looking at.

    What the reading LEARNED is written down even here, and one thing can be
    learned past a park: the base's identity. A remote that would not answer
    records no base at all, so the first pass that finally gets an id for one
    is what gives every retry after it an exact object to ask for -- dropped
    here, the next pass asks the remote again and freezes whatever the branch
    has moved to since, which is a different pair under the same generation.

    Nothing else is written and nothing is counted. The bound is spent, so a
    count past it measures nothing, and a record that says what it already
    said is a pinned write bought for no reader.
    """
    log.warning(
        "issue=#%d still cannot measure its committed candidate %s (%s); "
        "holding the tick without a second notice",
        gate.issue.number, generation.candidate_sha, failure,
    )
    if _late_state.read_late_generation(gate.state).base_sha != (
        generation.base_sha
    ):
        _persisted(gate, generation)
    _emit(gate, generation, _events.measurement_failure_event(failure, detail))
    return True


def _records_the_notice(
    gate: _records._Gate, generation: LateGeneration, failure,
) -> None:
    """Write the member a notice is about to name, before it is said.

    That order is what makes the notice the only one: every tick is a fresh
    process, so a member said and not written down is one the next poll says
    again, once a poll, for as long as the transport or the checkout stays
    where it is.

    A record already naming it pays no write -- the road that spends the bound
    puts the member down with the count, in the one write that carries both --
    and a refusal that froze no candidate writes nothing at all: a pinned
    cycle with no commit under it freezes nothing, reconciles nothing, and is
    read as a live cycle by the guard that ends one when the issue closes.
    Nothing re-enters such a park either, so there is no second notice for it
    to suppress.
    """
    if not generation.candidate_sha:
        return
    if _late_state.read_late_generation(
        gate.state,
    ).measurement_failure == failure:
        return
    _persisted(gate, _announced(generation, failure))


def _lost_reading(
    gate: _records._Gate, generation: LateGeneration, failure,
    detail: str = "",
) -> bool:
    """Count one reading the transport lost, and end the tick either way.

    The bounded road into the park above, taken by the two steps that reach a
    base rather than read one. It is bounded rather than absent because those
    steps clear themselves: a remote that would not answer and a fetch that
    brought nothing back are a network, a token, or a host that was down, and
    the next tick is very often the whole of the fix. Spending a human on the
    first of them spends them on something nobody had to do.

    So a miss inside the bound does exactly one thing -- it goes on the record
    -- and deliberately does nothing else: no `awaiting_human`, no reason, and
    no comment, which leaves the pinned pair exactly as a retry finds it and
    lets the next tick re-enter that same pair on both roads with no agent
    behind it. Past the bound the ordinary park takes it, because a base still
    unreachable that many readings later is not one this process is going to
    reach, and committed work is waiting behind a reading that will not
    happen.

    The count goes down BEFORE anything is reported or said, and that order is
    the bound itself: every tick is a fresh process, so a miss lost to a crash
    in that window is a miss nothing remembers -- and a retry that cannot
    remember is not bounded at all. What is written always names a candidate,
    since both callers reach here holding the pair they froze.

    A park this owner already took OVER THIS PAIR ends the counting outright:
    the bound is spent, the human it asked has been asked, and the reading is
    retried each tick only so the transport coming back settles it without
    one. The reading is still reported, and whether it is also SAID is the
    announce-once guard above rather than this road's: a step that park
    already named is a repeat, and one it did not is a notice nobody has made.
    What clears the park is a reading that succeeds, or the human's own bare
    continue, which drops the reason before the gate is entered and so buys
    exactly one more counted attempt.

    The member that goes on the record is the one a notice NAMED, and the
    reading that spends the bound writes it in the same write as the count:
    the two are one fact -- this reading ran the retries out and is about to
    be said -- so a crash between them would leave a mention nothing could
    tell from a repeat. A quiet miss writes only the count, because it says
    nothing to anybody: the step it stopped at recorded there would be a
    notice the guard thinks was made, and the miss that finally spends the
    bound would find its own step already down and hand the issue over
    without a word.

    A park standing over some OTHER pair is a spent one, and it is retired
    here rather than obeyed. The commonest way to reach one is the opposite
    reply to that continue: a human answers the park with guidance, the
    developer is resumed, and what it commits is a fresh candidate this park
    was never about. Read as this pair's, the miss over that new commit would
    be dropped on the floor -- nothing persisted, nothing reported, and the
    pinned record still naming work the branch has moved past for the next
    tick to reconcile against.
    """
    if _stands_over(gate, generation):
        return _unmeasured(gate, generation, failure, detail)
    # Nobody is waiting on this pair, so no park may outlive the miss about to
    # be counted: a reason standing with its latch already spent -- what a
    # resume leaves -- still freezes the branch out of base sync and still
    # tells every announce-once guard a human has been notified.
    _retire_spent_park(gate.state)
    missed = _one_more_miss(generation, failure)
    announcing = not _retries_quietly(missed, failure)
    if announcing:
        missed = _announced(missed, failure)
    _persisted(gate, missed)
    if announcing:
        return _unmeasured(gate, missed, failure, detail)
    log.warning(
        "issue=#%d could not reach the base its committed candidate %s is "
        "measured against (%s); re-reading the same pair on the next tick "
        "(%d of %d readings lost)",
        gate.issue.number, missed.candidate_sha, failure,
        missed.measurement_miss_count,
        _state._MEASUREMENT_MISSES_BEFORE_PARK,
    )
    _emit(gate, missed, _events.measurement_failure_event(failure, detail))
    return True


def _stands_over(gate: _records._Gate, generation: LateGeneration) -> bool:
    """Whether a human is still waiting on a notice about THIS pair.

    Two things have to be true, and each rules out a different way of
    suppressing a mention nobody has made. The park has to be one somebody is
    still waiting on -- the LATCH, not the reason beside it, since a resume
    consumes the latch and leaves the reason standing, and a human who
    answered with guidance has spent the notice they were sent rather than
    still being owed it. And the pair has to be the one the park was taken
    over, read off the pinned record, since a candidate the branch has moved
    past is work that park was never about. Either way the fresh start owes
    its own bounded retry rather than inheriting one already spent.
    """
    if not gate.state.get(_state._AWAITING_HUMAN):
        return False
    if gate.state.get(_state._PARK_REASON) != PARK_MEASUREMENT_FAILED:
        return False
    recorded = _late_state.read_late_generation(gate.state)
    return recorded.candidate_sha == generation.candidate_sha


def _announced(generation: LateGeneration, failure) -> LateGeneration:
    """The record a notice naming this step leaves behind.

    The field is what the thread has been TOLD, so it is written by the two
    roads that tell somebody and by nothing else. Read that way it answers the
    only question the retry after it has: does the sentence already on this
    issue cover the step this reading stopped at?
    """
    return replace(generation, measurement_failure=failure)


def _one_more_miss(generation: LateGeneration, failure) -> LateGeneration:
    """The record one lost reading leaves, where the bound counts it.

    A step outside the bound is handed on untouched. The count is what says
    how close this pair is to being handed to a human, so a failure nothing
    retries may not spend one of the readings a transport fault is owed.

    The count and nothing beside it. What a quiet miss stopped at is said to
    the log and to both streams and to no human at all, and the member on the
    record is the one a human was TOLD -- so writing this reading's step there
    would leave the announce-once guard reading a notice nobody made.
    """
    if failure not in _TRANSPORT_STEPS:
        return generation
    return replace(
        generation,
        measurement_miss_count=generation.measurement_miss_count + 1,
    )


def _retries_quietly(missed: LateGeneration, failure) -> bool:
    """Whether this miss is one the next tick takes again without a human."""
    return (
        failure in _TRANSPORT_STEPS
        and missed.measurement_miss_count
        <= _state._MEASUREMENT_MISSES_BEFORE_PARK
    )


def _reached(generation: LateGeneration) -> LateGeneration:
    """The record a base this host really holds leaves: no miss outstanding.

    A freeze that succeeded is what the count exists to be ended by, and the
    end has to be recorded rather than assumed. Carried past it, readings lost
    to a transport that has since recovered would be spent on the next fault
    instead: a pair that lost three of them and then measured would hand the
    issue to a human on the first hiccup after that.

    The count and only it. Reaching the base is not the end of the steps a
    reading can stop at -- the diff still has to be pinned, taken and read --
    and the member beside the count is what a NOTICE named, so dropping it
    here would lose the record of what a human was told on the very tick that
    reaches the base, and the diff failure behind it would be announced afresh
    on every poll for as long as the base stayed reachable. `_measured` is
    where it goes, once the reading it describes has actually happened.
    """
    return replace(generation, measurement_miss_count=0)


def _measured(generation: LateGeneration) -> LateGeneration:
    """The record a reading that HAPPENED leaves: nothing outstanding at all.

    The end of every step a measurement can stop at, which is the first point
    a member on this record describes a refusal that is over. So it goes here,
    before the verdict settles on the record -- and the count with it, since
    the same reading ended the row of lost ones.

    Before this and not after: the settlement WRITES this record, and an
    oversized candidate's survives the write to be adjudicated from. Cleared
    afterwards instead, the pinned comment would carry a step a human was told
    about into an adjudication where nothing is refusing anything, and the
    announce-once guard would read it as a sentence still standing on a thread
    whose park was retired by this very verdict.
    """
    return replace(
        generation, measurement_miss_count=0, measurement_failure=None,
    )


def _retire_spent_park(state: PinnedState) -> None:
    """Drop a measurement park this attempt is the answer to, latch and all.

    The reason is durable and so is the flag beside it, so without this a park
    a fresh reading has superseded travels on -- into the stage the
    publication hands the issue to, where it is state describing a step
    nothing is waiting on.

    Called by the two owners that ANSWER the question it was taken for -- the
    verdict a count settles, and the verdict a commit this workflow already
    decided about needs no count for -- rather than by the gate they sit
    behind. Entering the gate is not an answer: the reading can miss again,
    and a retirement taken on the way in is one a durable write in that window
    makes permanent, leaving an unparked issue whose reading still has not
    happened and whose next miss starts the bound over. Every other exit
    either takes a park of its own with the reason it fails for NOW or leaves
    this one standing because it is still true.

    The LATCH goes with the reason, and it is the half that decides whether
    the reading was worth taking. A reconciliation the dispatcher drives has
    no run behind it to clear the flag, so a pair that measured small would
    retire its record, record the commit as owed a push, and hand the tick to
    a source stage that reads `awaiting_human` and takes its parked road --
    waiting for a reply to a question this very tick answered, while the
    approved commit sits unpushed. Only a measurement park is retired here, so
    a question, a dirty tree, or a timeout is left exactly where it stands.
    """
    if state.get(_state._PARK_REASON) == PARK_MEASUREMENT_FAILED:
        state.set(_state._PARK_REASON, None)
        state.set(_state._AWAITING_HUMAN, False)


def _retire_settled_park(
    state: PinnedState, recorded: LateGeneration,
) -> bool:
    """Drop a measurement park a settled split's own record provoked.

    True where one was standing, so the caller knows it owes the write. Left
    to the caller for the reason `_retire_spent_park` leaves it there: the
    tick that clears a park has its own write to ride out on, and this domain
    does not put two where one will do.

    The park is this domain's, and on a record whose candidate has already
    become children it is this domain's own false positive: the group the
    retirement keeps is there for the releases and the branch delete the
    umbrella still owes, not for a reading anybody is waiting on. Left
    standing it is an issue reading as parked for a human with nothing for a
    human to answer -- and the reason is durable, so the pre-tick base refresh
    goes on holding the branch it names for as long as the flag does.

    Only the measurement park is retired, for the reason every other
    retirement of it gives: a question, a rejected child, or a child somebody
    closed by hand is a park with an answer still owed, and this record says
    nothing about any of them.
    """
    if not recorded.split_has_settled:
        return False
    if state.get(_state._PARK_REASON) != PARK_MEASUREMENT_FAILED:
        return False
    _retire_spent_park(state)
    return True


def _retire_superseded_park(state: PinnedState) -> None:
    """Drop a park the adjudication is taking the issue out of.

    A hold hands every later tick to the late coordinator, and what the issue
    is waiting on from that moment is a verdict rather than whatever the park
    asked a human about. Left standing the flag reaches the coordinator as an
    issue already parked -- its own parked dispatch fires on a mention nobody
    made about the question now open -- and the reason beside it describes a
    step no one is retrying. Every road into a hold either had no park or has
    one this hold supersedes, so the clear is unconditional.
    """
    state.set(_state._AWAITING_HUMAN, False)
    state.set(_state._PARK_REASON, None)


def _recorded_candidate(state: PinnedState) -> str:
    """The commit this issue's record names, or "" where none does.

    Published for the disposition beside this owner, which needs the floor a
    park left on the branch: commits already there when a resumed run started
    are not that run's, and reading them as its own would publish work an
    agent's clarifying question was asked INSTEAD of.
    """
    return _late_state.read_late_generation(state).candidate_sha


def _approved_commit(state: PinnedState) -> str:
    """The commit an approval owes a publication for, or "" where none does.

    Published for every owner that has to know a commit is already DECIDED.
    An approval -- the retirement a small candidate earns, the exemption a
    `single` verdict records -- drops the generation that named the commit
    and licenses a push that has not run yet, so between the two this is what
    says which commit the issue is still waiting on. Read fail-closed like
    every other late commit field: only a whole object id is one, so a
    hand-edited value is no approval rather than an unmeasured publication.
    """
    return _payloads.as_hex(
        state.get(_state._APPROVED_SHA), _formats.COMMIT_LENGTHS,
    ) or ""


def _approved_lease(state: PinnedState) -> str:
    """The head a published approval was frozen against, or "" where none was.

    The other half of an approval taken on the published side, and the half
    the retry after a failed push cannot re-derive: the generation that froze
    the pull request's head was retired by the write that approved the
    commit, and re-reading the pull request answers with wherever it has
    moved to since. Read fail-closed like every other late commit field.

    Empty is the ordinary answer and means a pre-publication approval -- what
    every implementing-seam approval is -- whose push correctly takes its own
    reading of the remote.
    """
    return _payloads.as_hex(
        state.get(_state._APPROVED_LEASE), _formats.COMMIT_LENGTHS,
    ) or ""


def _approve(state: PinnedState, candidate_sha: str, lease: str) -> None:
    """Record the commit a publication is owed, and what it is pinned to.

    The pair is written together because it is spent together and means
    nothing apart: a lease with no approval names a head nobody owes a push
    for, and an approval whose lease was dropped is the one that force-pushes
    over whatever the pull request has become.
    """
    state.set(_state._APPROVED_SHA, candidate_sha)
    state.set(_state._APPROVED_LEASE, lease or None)


def _forget_approval(state: PinnedState) -> None:
    """Drop a debt that is paid, superseded, or being adjudicated instead.

    What the route still owed goes with it. Those obligations outlive the
    generation that froze them only so the tick that finally lands this commit
    can close them; past that push there is nothing left to close, and a group
    left standing would be restored by the next approval on this issue and
    applied to a round it was never owed for.
    """
    state.set(_state._APPROVED_SHA, None)
    state.set(_state._APPROVED_LEASE, None)
    _late_state.write_late_spends(state, ())


def _published_commit(state: PinnedState) -> str:
    """The commit this stage last pushed, or "" where none was.

    Published beside the approval for the owner that has to tell a candidate
    nobody has ruled on from one this stage already put on a pull request. The
    two are the same window read from its two ends: the approval says a push
    is owed, and this says one was made, so between the push and the relabel
    the second is what says the size question has been answered AND acted on.
    Read fail-closed like every other late commit field, so a hand-edited
    value is no publication rather than an unmeasured one.
    """
    return _payloads.as_hex(
        state.get(_state._PUBLISHED_SHA), _formats.COMMIT_LENGTHS,
    ) or ""


def _published_lease(state: PinnedState) -> str:
    """The head the recorded publication replaced, or "" where none is named.

    What scopes the receipt beside it to one publication attempt. A receipt is
    never cleared, so on its own it goes on naming a commit this stage pushed
    rounds ago and answers "this tick's push landed" for any pull request
    somebody rewound onto it. The head it REPLACED is the fact that dates it,
    and a caller that froze its own head is what compares the two.

    Read fail-closed like every other late commit field, and empty is a
    receipt that vouches for no moved head at all -- an initial publication,
    which froze no head, or one written before this pair was recorded.
    """
    return _payloads.as_hex(
        state.get(_state._PUBLISHED_LEASE), _formats.COMMIT_LENGTHS,
    ) or ""


def _publication_from(state: PinnedState, head: str) -> str:
    """The commit recorded as pushed FROM this head, or "" where none is.

    The receipt and its head asked as the one question every caller of them
    actually has: is the publication this record names the one I am about to
    act on? Neither half answers it. A receipt is never cleared, so on its own
    it goes on naming a commit this stage pushed rounds ago and vouches for
    any pull request somebody rewound onto it; a head with no receipt beside
    it names no push at all. Together they date one push to one attempt, and
    a caller that froze its own head is what the date is checked against.

    A caller with no head of its own is claiming nothing here, and gets "".
    """
    if not head or _published_lease(state) != head:
        return ""
    return _published_commit(state)


def _record_publication(
    state: PinnedState, published: str, superseded: str,
) -> None:
    """Record the commit a push put on the remote, and the head it replaced.

    The pair is written together for the reason the approval's is, and the
    danger is the mirror image: a receipt whose head was dropped is the one
    that vouches for a publication somebody else moved, so the second half is
    written on EVERY receipt -- cleared where there is no head to name rather
    than left for the next receipt to inherit from the last.
    """
    state.set(_state._PUBLISHED_SHA, published)
    state.set(_state._PUBLISHED_LEASE, superseded or None)


def _persisted(gate: _records._Gate, generation: LateGeneration) -> None:
    """Write the generation this step reached, and the state around it.

    What the caller's hold owes rides the same write, because the freeze is
    durable and the count that follows it is not: a tick that dies in between
    leaves a pair for the reconciliation ahead of the next handler to answer,
    and that tick has no run behind it to re-derive a reviewer round, a
    cleared bookmark, or a stage tail from. Written after the generation and
    inside its own key group, so the retirement that ends the pair drops it in
    the same write.

    Only while the pair still AWAITS its count, which is exactly the window it
    pays for. A record carrying a number has been answered -- the routed hold
    that carries it spent this on the way past -- and rewriting it there would
    leave a spent claim on the comment for a later reader to apply twice.

    A measurement park the new record moves PAST goes out in this same write,
    because the two are read as one afterwards: a later tick asks whether the
    park standing is the one this pair was parked for, and answers by
    comparing it against the recorded candidate. Left to the verdict alone,
    the window between this write and that one is a crash away from a park
    taken over one commit sitting beside a record naming another -- which the
    next tick reads as that pair's own, holding every later reading of it
    silently, counting none of them, and never reaching the notice a human is
    owed. Bound here, the comment can never say two things at once.
    """
    _unbound_park(gate.state, generation)
    _late_state.write_late_generation(gate.state, generation)
    if generation.additions is None:
        _late_state.write_late_spends(gate.state, gate.spends.fields)
    gate.gh.write_pinned_state(gate.issue, gate.state)


def _unbound_park(state: PinnedState, generation: LateGeneration) -> None:
    """Retire a measurement park the record being written moves past.

    Only a park over some OTHER candidate: one taken over the pair still being
    written is exactly the park that has to survive, since the reading it was
    taken for still has not happened. A record that names no candidate at all
    is no claim about which pair is parked, so it leaves the park alone.
    """
    if not generation.candidate_sha:
        return
    if state.get(_state._PARK_REASON) != PARK_MEASUREMENT_FAILED:
        return
    if _late_state.read_late_generation(state).candidate_sha == (
        generation.candidate_sha
    ):
        return
    _retire_spent_park(state)


def _emit(
    gate: _records._Gate, generation: LateGeneration, event: _events.LateEvent,
) -> None:
    """Report one late event from the stage the measurement happened in.

    Which stage that is comes off the entry the call was taken on rather than
    off this package's own name: the same gate runs at the seam that publishes
    a pull request for the first time and at the one that pushes to a pull
    request the remote already carries, and a record filed under
    `implementing` for a reading taken in `fixing` would put a measurement in
    a stage no developer of it ever ran under.
    """
    stage = _state._IMPLEMENTING_STAGE
    if gate.entry is not None:
        stage = gate.entry.stage
    _telemetry.emit_late_event(gate.gh, event, generation, stage=stage)


def _answers_the_measurement_park(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> list:
    """The bare continues a human has written on a measurement park, if any.

    Empty for everything else, and each exclusion is its own answer. An issue
    parked for another reason is not this park's to retry; a thread with
    nothing new on it is a human who has not replied yet; and a reply carrying
    real words is guidance, which belongs to the ordinary resume that feeds it
    to the developer rather than to a reading taken behind their back.

    A bare `/orchestrator continue` is the one reply that means "the step you
    could not take, take again": the failure was a reading rather than a
    question, so what it earns is the same pair measured once more and no
    agent at all.
    """
    if state.get(_state._PARK_REASON) != PARK_MEASUREMENT_FAILED:
        return []
    if not state.get(_state._AWAITING_HUMAN):
        return []
    replies = filter_trusted(
        gh.comments_after(issue, state.get(_state._LAST_ACTION_COMMENT_ID)),
    )
    if not replies or not _messages._parse_orchestrator_continue(replies):
        return []
    if not all(
        _messages._is_bare_orchestrator_continue(reply) for reply in replies
    ):
        return []
    return replies
