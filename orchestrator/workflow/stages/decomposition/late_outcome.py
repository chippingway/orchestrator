# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a finished late run becomes, and the order it becomes it in.

The half of the late mode that reads a reply and settles what it decided,
split from the coordinator that produces one the way `outcomes.py` is split
from `run.py` beside it. The parks every late exit hands the issue back
through live here too, because the ordering rule they all obey is this
owner's: the durable write goes out before the external effect, never after.

That rule is what a completed adjudication is worth. The agent has already
been paid for by the time a reply is read, so a crash between reading it and
recording it costs a second run of an agent that already answered. The result
is therefore written and persisted BEFORE anything is posted, and the
announcement a question owes the issue is reconciled from that record on a
later tick rather than being the only place the outcome exists. What the
narrow crash window between the post and the write can still cost is one
repeated comment -- the same window every park in this repository has -- and
never the run.

The lineage bound is enforced here rather than in the parser, because it is a
property of the generation and not of the reply. A structurally valid split
proposed at the bound is recorded as the categorized question it actually is:
the workflow is asking a human, the recorded outcome says so, and the next
tick does not pay for another agent to propose the same forbidden split.

What this owner deliberately does NOT do is publish. It records a verdict,
announces a question, and returns; restoring or superseding the held plan PR,
creating children, and pushing an accepted candidate all belong to the steps
that act on the verdict.
"""
from __future__ import annotations

import logging

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.late_split import events as _events
from orchestrator.workflow.late_split import formats as _formats
from orchestrator.workflow.late_split import state as _late_state
from orchestrator.workflow.late_split import telemetry as _telemetry
from orchestrator.workflow.late_split.models import LateFailure, LateVerdict
from orchestrator.workflow.stages.decomposition import (
    late_reply as _late_reply,
)
from orchestrator.workflow.stages.decomposition import (
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

_AWAITING_HUMAN = "awaiting_human"

_PARK_REASON = "park_reason"

# The issue-wide record of what the workflow has already acted on. Shared with
# every other stage, which is why this mode has to keep it moving: a reply this
# mode read and acted on is one the later validating -> in_review handoff must
# not find again as fresh PR feedback.
_LAST_ACTION_COMMENT_ID = "last_action_comment_id"

# Every way this mode hands an issue back, spelled once because each is a
# durable pinned value and because the set below is read against them.
PARK_HOLD_FAILED = "late_plan_pr_hold_failed"
PARK_INCOMPLETE = "late_generation_incomplete"
PARK_WORKTREE_MISSING = "late_worktree_missing"
PARK_WORKTREE_MUTATED = "late_worktree_mutated"
PARK_TIMEOUT = "late_adjudicator_timeout"
PARK_UNPARSED = "late_manifest_invalid"
PARK_UNRECORDABLE = "late_result_unrecordable"
PARK_QUESTION = "late_question"
PARK_CONTENT_DRIFT = "late_content_drift"
PARK_REVISION_DIRTY = "late_revision_dirty"
PARK_REVISION_UNMEASURED = "late_revision_unmeasured"
PARK_REVISION_UNANSWERED = "late_revision_unanswered"

# The parks a fresh attempt answers, and therefore retires before it runs. A
# hold that failed has now been reconciled, a worktree that was gone is back, a
# run that timed out or answered unusably is about to be re-run. The five left
# out are the ones no retry answers, because none of them is a step that
# failed: `PARK_QUESTION` is the announcement itself, and the four content
# parks are the workflow waiting to be told what an edited scope, a worktree
# the developer left changed, a candidate nobody could measure, or a developer
# that changed nothing and vouched for nothing now means. Retiring one of those
# would drop the very state the next tick reads to tell a human's answer from
# the silence before it.
_SUPERSEDED_PARKS = frozenset((
    PARK_HOLD_FAILED,
    PARK_INCOMPLETE,
    PARK_WORKTREE_MISSING,
    PARK_WORKTREE_MUTATED,
    PARK_TIMEOUT,
    PARK_UNPARSED,
    PARK_UNRECORDABLE,
))

_UNPARSED_PARK = (
    "the late decomposer did not return a usable "
    "`orchestrator-late-manifest` block ({reason}), so nothing was decided "
    "about this issue's oversized committed candidate."
)

_QUESTION_PARK = ":mag: the late decomposer is asking ({category}): {asked}"

_UNRECORDABLE_PARK = (
    "the late decomposer decided something this issue's pinned state cannot "
    "hold -- a question or a child manifest past the size one orchestrator "
    "comment may carry. Nothing was recorded and nothing was published, "
    "because half an outcome is not one. This oversized candidate needs a "
    "human to split it by hand."
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
        _park(
            context,
            _UNPARSED_PARK.format(reason=parse_error),
            reason=PARK_UNPARSED,
        )
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

    An outcome the record could not hold is the one case that does not get
    announced: nothing durable stands behind it, so acting on it would leave
    the issue decided in a way no later tick could see. It parks instead.
    """
    kept = _late_session._record_late_result(context.state, adjudication)
    _persist(context)
    _emit_verdict(context, adjudication)
    if not kept:
        log.error(
            "issue=#%d the late outcome does not fit the pinned comment; "
            "refusing to record part of it",
            context.issue.number,
        )
        _park(
            context, _UNRECORDABLE_PARK, reason=PARK_UNRECORDABLE,
        )
        return _finished(context, _LateDisposition.PARKED)
    _announce(context, adjudication)
    return _LateAdjudicationRun(
        disposition=_LateDisposition.DECIDED,
        generation=context.generation,
        run=_late_session._read_late_run(context.state),
        adjudication=adjudication,
    )


def _announce(
    context: _LateContext, adjudication: _LateAdjudication,
) -> bool:
    """Post the question this outcome owes the issue, if it owes one.

    Returns whether it posted, which is also whether it persisted: the park
    it goes through commits everything staged with it, so a caller with its
    own staged change learns here whether it still owes a write.

    Read off the adjudication rather than off the record, so what the issue
    is told is what the agent actually wrote. The two agree -- an outcome is
    refused rather than shortened -- but the announcement is not the record's
    to paraphrase.

    A verdict that asks nothing announces nothing, and a question the issue is
    already waiting on a human for is not repeated.
    """
    if not adjudication.question or context.state.get(_AWAITING_HUMAN):
        return False
    _park(
        context,
        _QUESTION_PARK.format(
            category=adjudication.category, asked=adjudication.question,
        ),
        reason=PARK_QUESTION,
    )
    return True


def _reused(
    context: _LateContext, run: _LateRun, *, retired: bool,
) -> _LateAdjudicationRun:
    """Report an answer this tick did not have to earn.

    Two things can still be owed here. The announcement, if the tick that
    recorded the question died before posting it: `awaiting_human` is what
    decides that, and the park writes it in the same breath as the comment, so
    an outcome recorded and never said is said by the next tick from the
    question the record kept rather than by another agent run.

    And the write itself. This is the one branch that returns without doing
    anything else, so a park retired into memory here and not persisted is a
    park still standing on the issue -- durably claiming a human is owed
    something, on an issue whose answer is already recorded.
    """
    announced = False
    if run.verdict == LateVerdict.QUESTION:
        announced = _announce(
            context, _late_session._recovered_adjudication(run),
        )
    if retired and not announced:
        _persist(context)
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
    """
    _late_session._record_late_session(context.state, agent_result)
    _park(context, message, reason=reason)
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


def _park(context: _LateContext, message: str, *, reason: str) -> None:
    """Hand the issue back to a human and commit everything staged with it.

    The reason is written durably beside the flag, which the shared park
    deliberately clears: without it, an issue parked here is one nothing can
    tell from an issue parked by any other stage, and the next late attempt
    could neither retire its own park nor leave somebody else's alone.

    A park already standing for this same reason is not announced again. Every
    late failure is reconciled on each eligible tick -- that is what makes the
    retries idempotent -- so an unchanged one would otherwise say the same
    sentence to the same thread once a tick until a human arrived. The state
    is still written: what is suppressed is the notice, not the park.
    """
    if _stands_already(context, reason):
        log.info(
            "issue=#%d is already parked as %s; not repeating the notice",
            context.issue.number, reason,
        )
        context.state.set(_AWAITING_HUMAN, True)
        context.state.set(_PARK_REASON, reason)
        _persist(context)
        return
    _guards._park_awaiting_human(
        context.gh,
        context.issue,
        context.state,
        f"{config.HITL_MENTIONS} {message}",
        reason=reason,
    )
    context.state.set(_PARK_REASON, reason)
    _persist(context)


def _stands_already(context: _LateContext, reason: str) -> bool:
    """Whether this issue is already parked for exactly this reason.

    Asked of what the tick FOUND, not only of what it has staged. A park this
    tick retired into memory and is now re-taking for the same reason is the
    same park -- the step it named failed again, nothing about the issue moved
    between them, and the human it mentioned has already been told.

    "Nothing moved between them" is what the memory really claims, which is why
    the run that could move something clears it. Past a spawn the reason is no
    longer enough to call two parks the same: an agent answered, and a second
    categorized question or a second unusable reply says something the first
    notice did not. Suppressing those would leave an outcome recorded, durable,
    and never announced -- so only the reconciliation retries that spawn
    nothing keep the memory that quiets them.

    A park somebody cleared is not standing, whatever reason it carried, so an
    issue a human un-parked is announced to again rather than silently
    re-parked.
    """
    if context.retired_park == reason:
        return True
    if not context.state.get(_AWAITING_HUMAN):
        return False
    return context.state.get(_PARK_REASON) == reason


def _retire_park(context: _LateContext) -> bool:
    """Clear a late park this attempt has already answered.

    A park is a claim that the issue is waiting on a human. Once the step that
    failed has been reconciled the claim is stale, and leaving it standing is
    not harmless: the announcement a question earns is suppressed by exactly
    this flag, so a hold that failed once would silence a categorized question
    -- decided, durable, and never said out loud.

    Which is why this runs the moment the hold reconciles rather than beside
    the spawn. The question being silenced need not be one this tick produced:
    a run whose result persisted and whose comment then failed leaves an
    announcement owing, and a hold that failed in between would bury it under
    a park that has nothing to do with it.

    Only this mode's own parks, and only the ones an attempt answers. A park
    another stage left is not this one's to retire, and the question park is
    not stale: nothing here has answered it.

    Returns whether anything was retired. The write belongs to the caller,
    as it does for every other state this mode stages, and the caller that
    stages nothing else has to know it now owes one. What was retired is kept
    on the tick, so a park re-taken for the same reason is recognized as the
    one already announced rather than announced again.
    """
    standing = context.state.get(_PARK_REASON)
    if standing not in _SUPERSEDED_PARKS:
        return False
    context.retired_park = standing
    context.state.set(_AWAITING_HUMAN, False)
    context.state.set(_PARK_REASON, None)
    return True


def _mark_replies_read(context: _LateContext, through) -> None:
    """Record the trusted conversation this tick acted on as read, issue-wide.

    The late fingerprints are this mode's own bookkeeping; the watermark moved
    here is everybody's. A reply that resolved a park, certified a candidate,
    or reopened a question has been ACTED on, and leaving the shared watermark
    behind would let the validating -> in_review handoff read the same comment
    as fresh PR feedback -- routing the pull request to `fixing` over an answer
    this mode already spent, or resuming the developer on input it handled.

    `through` is the highest TRUSTED comment folded in, so an untrusted comment
    sitting above it stays unconsumed exactly as it does on every other resume:
    nothing an outsider posts is marked read on their behalf. A one-way ratchet,
    because a park notice or another stage may already have moved it further.
    """
    if not _formats.whole_number(through):
        return
    prior = context.state.get(_LAST_ACTION_COMMENT_ID)
    if not _formats.whole_number(prior) or through > prior:
        context.state.set(_LAST_ACTION_COMMENT_ID, through)


def _answer_park(context: _LateContext) -> None:
    """Clear the park a human has now answered.

    The counterpart to `_retire_park` for the parks no retry supersedes. Those
    stand until somebody says something, so what clears them is an answer
    rather than another attempt -- and the caller that took the answer is the
    only thing that knows one arrived.

    Deliberately NOT remembered on the tick the way a retirement is. That
    memory exists to recognize a park re-taken unchanged, and an answered park
    is never that: the human said something, something ran because they did,
    and whatever it parks on next is news even when it carries the same reason.
    A second question is a different question, and remembering the first would
    leave it recorded, durable, and never said out loud. The write belongs to
    the caller, as it does for every other state this mode stages.
    """
    context.state.set(_AWAITING_HUMAN, False)
    context.state.set(_PARK_REASON, None)


def _persist(context: _LateContext) -> None:
    """Write the generation this tick reached, and the state around it."""
    _late_state.write_late_generation(context.state, context.generation)
    context.gh.write_pinned_state(context.issue, context.state)


def _finished(
    context: _LateContext, disposition: _LateDisposition,
) -> _LateAdjudicationRun:
    """Report what this call did, with the run pinned state now records."""
    return _LateAdjudicationRun(
        disposition=disposition,
        generation=context.generation,
        run=_late_session._read_late_run(context.state),
    )
