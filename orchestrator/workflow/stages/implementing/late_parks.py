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
from orchestrator.workflow.stages.implementing import (
    late_records as _records,
    state as _state,
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
    unmeasured = _UNMEASURED_PARK
    if gate.entry is not None:
        unmeasured = _UNMEASURED_PUBLISHED_PARK
    return _parked(
        gate, generation, failure,
        unmeasured.format(mentions=config.HITL_MENTIONS, failure=failure),
    )


def _retire_spent_park(state: PinnedState) -> None:
    """Drop a measurement park this attempt is the answer to, latch and all.

    The reason is durable and so is the flag beside it, so without this a park
    a fresh reading has superseded travels on -- into the stage the
    publication hands the issue to, where it is state describing a step
    nothing is waiting on. Every exit below either publishes, hands the issue
    on, or takes a park of its own with the reason it fails for NOW, so there
    is nothing left for the old one to say.

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
    """
    _late_state.write_late_generation(gate.state, generation)
    if generation.additions is None:
        _late_state.write_late_spends(gate.state, gate.spends.fields)
    gate.gh.write_pinned_state(gate.issue, gate.state)


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
