# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a refusal costs, and the two sinks every one of them reaches.

One park shape for every reading the size gate could not take, because the
recovery is the same for all of them: the issue is handed back with the step
that failed named, the typed failure goes to the audit and analytics streams,
and a trusted bare `/orchestrator continue` re-reads rather than re-running
anything. The writes those steps ride out on are here too, since a park and a
persisted record are the two durable things this domain does.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
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
from orchestrator.workflow.late_split.models import LateFailure, LateGeneration
from orchestrator.workflow.stages.implementing import state as _state
from orchestrator.workflow.stages.implementing import (
    late_records as _records,
)

log = logging.getLogger("orchestrator.workflow")

PARK_MEASUREMENT_FAILED = "late_measurement_failed"

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

def _parked(
    gate: _records._Gate, generation: LateGeneration, failure, message: str,
) -> bool:
    """Record the typed failure on both sinks, then hand the issue back.

    Every reading that did not happen is reported, which is why the generation
    reaching here is one a caller has already made reportable: a candidate the
    gate could not even name has no record of its own yet, and the identity
    minted for it is what lets the failure be joined to the cycle a later
    freeze writes under the same number.
    """
    log.error(
        "issue=#%d committed work could not be measured (%s); parking rather "
        "than publishing an unadjudicated candidate",
        gate.issue.number, failure,
    )
    _emit(
        gate, generation,
        _events.LateEvent(
            family=_events.LateEventFamily.FAILURE,
            failure=LateFailure.MEASUREMENT_FAILED,
        ),
    )
    _guards._park_awaiting_human(
        gate.gh, gate.issue, gate.state, message,
        reason=PARK_MEASUREMENT_FAILED,
    )
    gate.state.set(_state._PARK_REASON, PARK_MEASUREMENT_FAILED)
    return True


def _unmeasured(
    gate: _records._Gate, generation: LateGeneration, failure,
) -> bool:
    """Park a candidate nobody could measure, loudly and with its reason.

    Never "small". What a failed `git` invocation writes to stdout is nothing,
    which is what a candidate that changes nothing writes too, so publishing
    on that reading is precisely how an unadjudicated implementation goes out.
    """
    return _parked(
        gate, generation, failure,
        _UNMEASURED_PARK.format(
            mentions=config.HITL_MENTIONS, failure=failure,
        ),
    )


def _retire_spent_park(state: PinnedState) -> None:
    """Drop a measurement park this attempt is the answer to.

    The reason is durable and the flag it sits beside is cleared by whatever
    resumed the developer, so without this a park a fresh disposition has
    superseded travels on -- into the stage the publication hands the issue
    to, where it is state describing a step nothing is waiting on. Every exit
    below either publishes, hands the issue on, or takes a park of its own
    with the reason it fails for NOW, so there is nothing left for the old one
    to say.
    """
    if state.get(_state._PARK_REASON) == PARK_MEASUREMENT_FAILED:
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


def _persisted(gate: _records._Gate, generation: LateGeneration) -> None:
    """Write the generation this step reached, and the state around it."""
    _late_state.write_late_generation(gate.state, generation)
    gate.gh.write_pinned_state(gate.issue, gate.state)


def _emit(
    gate: _records._Gate, generation: LateGeneration, event: _events.LateEvent,
) -> None:
    """Report one late event from the stage the measurement happened in."""
    _telemetry.emit_late_event(
        gate.gh, event, generation, stage=_state._IMPLEMENTING_STAGE,
    )


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
