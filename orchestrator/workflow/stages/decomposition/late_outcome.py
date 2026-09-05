# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a finished late run becomes, and the order it becomes it in.

The half of the late mode that reads a reply and settles what it decided,
split from the coordinator that produces one the way `outcomes.py` is split
from `run.py` beside it. What every exit here obeys is the ordering rule
`late_parks` owns beside it -- the durable write goes out before the external
effect, never after -- and what is here is the reading, the record it becomes,
and the three emissions that report it.

That rule is what a completed adjudication is worth. The agent has already
been paid for by the time a reply is read, so a crash between reading it and
recording it costs a second run of an agent that already answered. The result
is therefore written and persisted BEFORE anything is posted, and the
announcement a question owes the issue is reconciled from that record on a
later tick rather than being the only place the outcome exists. What the
narrow crash window between the post and the write can still cost is one
repeated comment -- the same window every park in this repository has -- and
never the run.

`_announce` is published for the same reason it is not called from the two
places that record an outcome: the owner guard runs between the record and
anything said out loud, so what posts a question is the step past that guard
rather than the step that wrote it down.

The lineage bound is enforced here rather than in the parser, because it is a
property of the generation and not of the reply. A structurally valid split
proposed at the bound is recorded as the categorized question it actually is:
the workflow is asking a human, the recorded outcome says so, and the next
tick does not pay for another agent to propose the same forbidden split.

The three emissions sit here rather than beside the sinks they reach. A
verdict, a typed failure, and the cancellation an owner read earns are each
written straight after the state they describe, and keeping them beside those
writes is what stops one of them reporting a step whose durable half never
landed.

What this owner deliberately does NOT do is publish. It records a verdict
and returns; announcing a question, restoring or superseding the held PR,
creating children, and pushing an accepted candidate all belong to the steps
that act on the verdict.

What holds this above the size a module is ordinarily kept to is the shape of
one completion: the five endings a reply reaches -- read, recorded, reused,
parked, announced -- the three emissions that report what each of them left,
and the completion write and the record it hands back that every one of them
closes on. That set is fixed by the verdict vocabulary rather than by what has
accumulated, and an emission moved away from the write it describes is exactly
the split that would let it report a step whose durable half never landed.
"""
from __future__ import annotations

import logging
from dataclasses import replace

from orchestrator.agents import AgentResult
from orchestrator.workflow.late_split import (
    events as _events,
    formats as _formats,
    telemetry as _telemetry,
)
from orchestrator.workflow.late_split.models import (
    IN_FLIGHT_PHASES,
    LateFailure,
    LatePhase,
    LateVerdict,
)
from orchestrator.workflow.stages.decomposition import (
    late_parks as _late_parks,
    late_reply as _late_reply,
    late_session as _late_session,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    _LateAdjudication,
    _LateAdjudicationRun,
    _LateContext,
    _LateDisposition,
    _LateRun,
)

log = logging.getLogger("orchestrator.workflow")

_DECOMPOSING_STAGE = "decomposing"

# The boundaries an owner-check claim can be standing at. `owner_check` is
# where a completion ordinarily leaves the record; a transaction re-entered
# after a crash keeps the boundary it interrupted instead -- the record's own
# rule refuses that rewind -- and its claim is as standing as any other.
_CLAIM_PHASES = frozenset((LatePhase.OWNER_CHECK, *IN_FLIGHT_PHASES))

_UNPARSED_PARK = (
    "the late decomposer did not return a usable "
    "`orchestrator-late-manifest` block ({reason}), so nothing was decided "
    "about this issue's oversized committed candidate."
)

_QUESTION_PARK = ":mag: the late decomposer is asking ({category}): {asked}"

_UNRECORDABLE_PARK = (
    "the late decomposer decided something this issue's pinned state cannot "
    "hold -- a question, an explanation of what stopped a split, or a child "
    "manifest past the size one orchestrator comment may carry. Nothing was "
    "recorded and nothing was published, because half an outcome is not one. "
    "This oversized candidate needs a human to split it by hand."
)

# What a split proposed at the lineage bound is recorded as. The bound is a
# safety invariant, so the outcome is not the split the agent asked for; it is
# the categorized question the workflow now owes a human, recorded as one so a
# later tick asks the human rather than the agent.
_AT_BOUND_QUESTION = _LateAdjudication(
    verdict=LateVerdict.QUESTION,
    category=_events.LateVerdictCategory.LINEAGE_BOUND,
    question=(
        "the late decomposer proposed splitting this issue, but its lineage "
        "is already as deep as automatic splitting goes. It has to land as "
        "one change or be split by hand."
    ),
)


def _decide(
    context: _LateContext, last_message: str,
) -> _LateAdjudicationRun:
    """Read the reply, refuse a split the lineage forbids, and record it."""
    adjudication, parse_error = _late_reply._parse_late_reply(last_message)
    if adjudication is None:
        _late_parks._stage_park(
            context,
            _UNPARSED_PARK.format(reason=parse_error),
            reason=_late_parks.PARK_UNPARSED,
        )
        _completed(context)
        return _finished(context, _LateDisposition.PARKED)
    if (
        adjudication.verdict == LateVerdict.SPLIT
        and not context.generation.may_split
    ):
        adjudication = _AT_BOUND_QUESTION
    return _recorded(context, adjudication)


def _recorded(
    context: _LateContext, adjudication: _LateAdjudication,
) -> _LateAdjudicationRun:
    """Persist one completed adjudication, then say what it decided.

    The persist is first and unconditional. Everything after it -- the two
    sinks, and the comment a question owes the issue -- is an external effect
    that a crash may repeat, and repeating one of those costs a duplicate
    record or a duplicate comment. Repeating what comes before it would cost
    another agent run against a candidate that has already been adjudicated,
    and a second run is free to decide differently.

    An outcome the record could not hold is the one case that never becomes
    an answer at all: nothing durable stands behind it, so acting on it would
    leave the issue decided in a way no later tick could see. It parks
    instead, and the park is staged BEFORE the write rather than after it, so
    the one write carries whichever of the two this run produced.

    What it deliberately does NOT do is announce. The announcement is an
    external effect on the issue, and whether the issue is still there is the
    owner guard's question -- which is asked between this write and anything
    said out loud, so a question is not posted to a thread somebody closed
    while the agent was answering it.
    """
    kept = _late_session._record_late_result(context.state, adjudication)
    if not kept:
        log.error(
            "issue=#%d the late outcome does not fit the pinned comment; "
            "refusing to record part of it",
            context.issue.number,
        )
        _late_parks._stage_park(
            context, _UNRECORDABLE_PARK, reason=_late_parks.PARK_UNRECORDABLE,
        )
    _completed(context)
    _emit_verdict(context, adjudication)
    if not kept:
        return _finished(context, _LateDisposition.PARKED)
    return _LateAdjudicationRun(
        disposition=_LateDisposition.DECIDED,
        generation=context.generation,
        run=_late_session._read_late_run(context.state),
        adjudication=adjudication,
    )


def _announce(
    context: _LateContext, adjudication: _LateAdjudication,
) -> None:
    """Post the question this outcome owes the issue, if it owes one.

    Called past the owner guard rather than beside the record, so a question
    is never posted to a thread this tick could not prove is still open. The
    park it goes through commits everything staged with it, so a caller has
    nothing left to write afterwards.

    Read off the adjudication rather than off the record, so what the issue
    is told is what the agent actually wrote. The two agree -- an outcome is
    refused rather than shortened -- but the announcement is not the record's
    to paraphrase.

    A verdict that asks nothing announces nothing, and a question the issue is
    already waiting on a human for is not repeated -- which is what a recorded
    question reaching this a second time relies on.
    """
    if not adjudication.question or _late_parks._stands_parked(context):
        return
    _late_parks._park(
        context,
        _QUESTION_PARK.format(
            category=adjudication.category, asked=adjudication.question,
        ),
        reason=_late_parks.PARK_QUESTION,
    )


def _reused(
    context: _LateContext, run: _LateRun, *, retired: bool,
) -> _LateAdjudicationRun:
    """Report an answer this tick did not have to earn.

    The announcement a recorded question still owes the issue is not made
    here: it is made past the owner guard, from the question the record kept,
    which is what lets an outcome recorded and never said be said by a later
    tick rather than by another agent run.

    What IS owed here is the write. This is the one branch that returns
    without doing anything else, so a park retired into memory and not
    persisted is a park still standing on the issue -- durably claiming a
    human is owed something, on an issue whose answer is already recorded.
    """
    if retired:
        _late_parks._persist(context)
    return _LateAdjudicationRun(
        disposition=_LateDisposition.DECIDED,
        generation=context.generation,
        run=_late_session._read_late_run(context.state),
        adjudication=_late_session._recovered_adjudication(run),
    )


def _parked_run(
    context: _LateContext,
    agent_result: AgentResult,
    message: str,
    *,
    reason: str,
) -> _LateAdjudicationRun:
    """Pin the session this run opened, then hand the issue back.

    Both parks that follow a finished run come through here, so the session a
    later resume has to land on is recorded at every exit that writes and at
    no exit that does not -- what the returned record claims is what the
    pinned comment holds.

    Staged rather than said, because the run this parks has already been paid
    for: the session and the park are made durable by the write below, and the
    notice waits for a read that proves the issue is still there.

    That write is this owner's own and not the guard's, which is the whole
    difference between a completion nobody has to pay for twice and one that
    can be lost. A timeout and a contaminated worktree are as finished as a
    verdict is -- the agent ran, the issue paid for it, and what it left is
    exactly as unrepeatable -- so what they decided goes down here, before
    anything that could fail to come back.
    """
    _late_session._record_late_session(context.state, agent_result)
    _late_parks._stage_park(context, message, reason=reason)
    _completed(context)
    return _finished(context, _LateDisposition.PARKED)


def _emit_verdict(
    context: _LateContext, adjudication: _LateAdjudication,
) -> None:
    """Report one adjudication on both sinks, or lose the record instead.

    The event contract is checked where the event is built, which is here
    rather than inside the emission, so the refusal it raises is caught here
    too: a record nobody should have written and a tick broken by the attempt
    to write it are both failures, and only the first one is recoverable.
    """
    try:
        decided = _events.LateEvent(
            family=_events.LateEventFamily.VERDICT,
            verdict=adjudication.verdict,
            category=adjudication.category,
            child_count=adjudication.child_count,
        )
    except _formats.InvalidLateValue as refused:
        log.error(
            "issue=#%d late verdict refused as an event (%s); nothing "
            "emitted", context.issue.number, refused,
        )
        return
    _telemetry.emit_late_event(
        context.gh, decided, context.generation, stage=_DECOMPOSING_STAGE,
    )


def _emit_failure(context: _LateContext, failure: LateFailure) -> None:
    """Report one typed late failure on both sinks."""
    _telemetry.emit_late_event(
        context.gh,
        _events.LateEvent(
            family=_events.LateEventFamily.FAILURE, failure=failure,
        ),
        context.generation,
        stage=_DECOMPOSING_STAGE,
    )


def _emit_measurement_failure(
    context: _LateContext, failure, detail: str,
) -> None:
    """Report a revision nobody could measure, with the step it stopped at.

    The same family and the same typed failure the size gate writes, so a
    reading that did not happen reads alike wherever it was taken -- and with
    the same two companions, because the question an operator asks of one of
    these is the question they ask of all of them: which step, and what did it
    say. A re-measurement is taken in a checkout an agent has been running in,
    so the step it stops at is the one thing telling a base a fetch cannot
    bring from a diff something in that tree made unreadable.
    """
    _telemetry.emit_late_event(
        context.gh,
        _events.measurement_failure_event(failure, detail),
        context.generation,
        stage=_DECOMPOSING_STAGE,
    )


def _emit_cancellation(context: _LateContext) -> None:
    """Report that this generation's owner was observed gone.

    Emitted after the cancellation is durable, like every other record here,
    so what a sink carries is a mark the cleanup can already read rather than
    a claim about a write that may not have landed. The family says everything
    on its own -- who was cancelled is the generation's own correlation -- so
    it carries no detail of its own.
    """
    _telemetry.emit_late_event(
        context.gh,
        _events.LateEvent(family=_events.LateEventFamily.CANCELLATION),
        context.generation,
        stage=_DECOMPOSING_STAGE,
    )


def _completed(context: _LateContext) -> None:
    """Write what a finished run left, and the read it now owes, as one thing.

    The last step of every completion and the first one that could survive it.
    A run that finished is not free to repeat -- the agent has been paid for,
    and a second one is free to decide differently -- so what it decided is
    durable before the tick does anything that might not come back. That is
    as true of a timeout, an unusable reply, an outcome too large to record,
    a contaminated worktree, and a reconciliation nobody could make as it is
    of a verdict: each is a completed run, and each leaves a park a later tick
    would otherwise neither find nor be able to rebuild.

    The owner read the completion now owes rides the very same write, and that
    is not a convenience. Deriving the obligation from the guard a step later
    means a tick that dies in between leaves a generation still reading as
    `adjudicating` -- no park, no claim, and a next tick that pays for another
    agent against a candidate this one already answered.

    Which is why this is the LAST step of a completion and never a step in the
    middle of one. Everything the completion staged -- the session, the park,
    the notice it owes, the recorded outcome -- is already in memory when this
    runs, so the one write carries all of it. A caller that staged something
    afterwards would be staging it into a write that has already happened.
    """
    context.generation = replace(
        context.generation.at_phase(LatePhase.OWNER_CHECK),
        owner_check_pending=True,
    )
    _late_parks._persist(context)


def _finished(
    context: _LateContext, disposition: _LateDisposition,
) -> _LateAdjudicationRun:
    """Report what this call did, with the run pinned state now records."""
    return _LateAdjudicationRun(
        disposition=disposition,
        generation=context.generation,
        run=_late_session._read_late_run(context.state),
    )
