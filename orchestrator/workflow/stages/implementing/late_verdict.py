# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a measured candidate earns, and what the record owes on the way.

Three endings and the retirement they share. A candidate at or below the
ceiling publishes, one past it is held under the adjudication label, and a
record the publication is going past is dropped -- durably, before the effects
it licenses, because the write that ends a generation has to land ahead of the
label that hands the issue on.

Which leaves a gap the same write has to fill. Between a retirement and the
push it licenses there is committed work on the branch and, without this,
nothing on the issue saying which commit it is -- so the commit a publication
is owed goes down beside the retirement and is spent by the handoff that
carries it. An adjudication takes it back off: a candidate being decomposed is
one nobody is publishing yet.
"""
from __future__ import annotations

import logging
from dataclasses import replace

from orchestrator.workflow.engine import (
    comments as _comments,
    observations as _observations,
    usage as _usage,
)
from orchestrator.workflow.late_split import (
    events as _events,
    state as _late_state,
)
from orchestrator.workflow.late_split.models import LateGeneration, LatePhase
from orchestrator.workflow.stages.implementing import late_parks as _parks
from orchestrator.workflow.stages.implementing import (
    late_records as _records,
    state as _state,
)
from orchestrator.workflow.state import WorkflowLabel

log = logging.getLogger("orchestrator.workflow")

_ROUTED_NOTICE = (
    ":triangular_ruler: this issue's committed implementation adds "
    "{additions} lines against a ceiling of {threshold}, so it is being "
    "adjudicated for its size before anything is published. Nothing has been "
    "pushed and no pull request carries it -- the commit `{candidate}` stays "
    "exactly where it is while `{label}` decides whether it ships as one "
    "change or becomes child issues."
)

def _settled(gate: _records._Gate, generation: LateGeneration) -> bool:
    """What a measured candidate earns: adjudication, or the ordinary push.

    Strictly past the ceiling, which is the record's own comparison: a
    candidate exactly at the configured value publishes, so the trigger cannot
    move by one line when the threshold is retuned.
    """
    if generation.is_oversized:
        return _routed(gate, generation)
    return _accepted(gate, generation)


def _accepted(gate: _records._Gate, generation: LateGeneration) -> bool:
    """Retire the generation a small candidate never needed, and publish.

    The record is dropped rather than left standing, and it has to be: a
    frozen candidate freezes this branch out of the ordinary base refresh, and
    a generation carried into the stages that close the issue is one a later
    guard reads as a live cycle a close should end.

    What outlives the drop is which cycle it was, and which COMMIT is still
    owed a publication. The cycle is what a close a poll observes inside this
    very window is adopted against, and what the next candidate on this issue
    mints its own cycle after, so no two attempts ever answer to the same
    number.

    The commit is the other half, and it rides the same write for the same
    reason: past the retirement nothing else on the issue names the work, and
    the push that carries it has not run yet. A tick that died in between
    would leave a branch with an unpublished commit on it and a record that
    has forgotten which one -- so a replacement host, which rebuilds the
    checkout from the base or the plan pull request, would find a head nothing
    contradicted and publish that instead. Recorded, the same host finishes
    the publication and a host without the commit parks for it.
    """
    log.info(
        "issue=#%d candidate %s adds %d lines against a ceiling of %d; "
        "publishing it as one change",
        gate.issue.number, generation.candidate_sha, generation.additions,
        generation.threshold,
    )
    gate.state.set(_state._APPROVED_SHA, generation.candidate_sha)
    return _retired(gate, generation)


def _supersedes_approval(gate: _records._Gate, candidate_sha: str) -> None:
    """Drop an approval this publication is going past.

    An approval names one commit and says that commit is owed a push. A tick
    publishing a DIFFERENT one has moved past the debt rather than paid it: a
    developer resumed on a human's guidance committed again, or an exemption
    one step over named some other commit, and the branch will not carry the
    approved commit as its tip. Left standing it would freeze this branch out
    of the ordinary base refresh for as long as the issue lives and park every
    later tick asking for a checkout back for work nobody is going to push.

    An approval naming the commit in hand is left exactly where it is: it is
    still owed, and the handoff that carries it is what spends it -- so a
    publication that parks instead comes back to a record that still says
    which commit the issue is waiting on.
    """
    approved = _parks._approved_commit(gate.state)
    if not approved or approved == candidate_sha:
        return
    log.info(
        "issue=#%d is publishing %s and no longer owes a push for approved "
        "commit %s; dropping it rather than holding the branch for work "
        "nothing is going to publish",
        gate.issue.number, candidate_sha or "a candidate it did not name",
        approved,
    )
    gate.state.set(_state._APPROVED_SHA, None)


def _superseded(gate: _records._Gate, recorded: LateGeneration) -> bool:
    """Drop a record this publication is going past, and publish without it.

    Two roads reach it and they are the same fact. With the switch off a fresh
    candidate does not enter the gate, so the record it supersedes describes a
    commit nothing is going to publish. And an exemption is the same shape one
    step over: the commit an adjudication accepted publishes without being
    measured, so a generation recorded over some OTHER candidate is a record
    about work this issue has moved past.

    Leaving either would freeze the branch out of the ordinary base refresh
    for as long as the issue lives, and carry a live-looking cycle into the
    stages that close the issue -- where the guard that ends one on a close
    reads it as still running. An issue that never entered the gate has
    nothing to drop and is left exactly as it was.

    True is a close that ended the cycle instead, which the caller reads the
    same way `_accepted` does: nothing is published.
    """
    if not recorded.is_present:
        return False
    log.info(
        "issue=#%d is publishing past recorded candidate %s without measuring "
        "it; retiring cycle %d rather than leaving it over work nobody is "
        "publishing",
        gate.issue.number, recorded.candidate_sha, recorded.cycle_id,
    )
    return _retired(gate, recorded)


def _retired(gate: _records._Gate, generation: LateGeneration) -> bool:
    """Drop this generation durably, BEFORE the publication it licenses.

    The write is the point, and it is one the caller cannot defer. What
    follows a retirement is `_on_commits`, which pushes a branch, opens a pull
    request, and moves the label to `workflow:validating` -- and the pinned
    write that would have carried the retirement comes after all of it. A tick
    that died in that window would leave a published pull request under
    `validating` over a generation that still says `measuring`: the branch
    frozen out of the base refresh for good, and a close on that issue read by
    the cancellation guard as a live cycle to end.

    So the record is dropped first and the effects follow it. The cost is one
    pinned write per candidate that publishes; what it buys is that no window
    exists in which the issue has moved on and its record has not.

    True is the answer that stops the publication: a close ended this cycle
    instead, so nothing may be pushed, opened, or handed to review on an issue
    nobody wants. It is asked in the two places a retirement can lose one. The
    latch is one -- a poll observed the close and could hand the reading to no
    worker, so no request of this tick's would show it. The retirement WRITE
    is the other and the subtler: it takes the cycle identity off the record,
    and everything that decides what a close is worth reads that identity, so
    a poll landing inside it finds an issue with nothing to end and drops the
    observation. The window advertises the cycle for exactly as long as the
    write runs, and what it saw is decided as it closes -- under the lock that
    closes it, so no interval is left for a reading to arrive unreported.

    A reading the window caught is answered by putting the generation BACK.
    It is still in this call's own memory, which is what makes that possible:
    it goes back exactly as it was and is cancelled from there, so what the
    ending reads is the cycle that actually ran rather than a refusal with no
    record under it. There is nothing to take back either -- the retirement
    runs ahead of every effect it licenses, so nothing has been published.
    """
    if _cancelled(gate, generation):
        return True
    retiring = _observations.retiring(
        gate.spec.slug, gate.issue.number, generation.cycle_id,
    )
    with retiring.held():
        _late_state.clear_late_generation(gate.state)
        _late_state.record_retired_cycle(gate.state, generation.cycle_id)
        gate.gh.write_pinned_state(gate.issue, gate.state)
    if not retiring.observed:
        return False
    log.warning(
        "repo=%s issue=#%d was observed closed inside the write retiring "
        "cycle %d; putting it back so the cancellation has something to end",
        gate.spec.slug, gate.issue.number, generation.cycle_id,
    )
    _marked(gate, generation)
    return True


def _cancelled(gate: _records._Gate, generation: LateGeneration) -> bool:
    """End this cycle where a close is already latched against the issue.

    Asked before the retirement rather than after, because the retirement is
    what makes the reading unanswerable: once the identity is off the record
    there is no cycle for the ending to be entered from, and the receipt a
    poll left on the thread has nothing to be adopted against.

    The mark is durable before it is reported, and it is the same mark the
    adjudication's own barriers write -- the cleanup that settles a cancelled
    cycle reads this record and cannot tell which barrier put it there.
    """
    if not generation.is_present or generation.cancelled:
        return False
    if not _observations.close_observed(gate.spec.slug, gate.issue.number):
        return False
    log.warning(
        "repo=%s issue=#%d was observed closed as its measured candidate was "
        "about to publish; ending cycle %d rather than pushing a branch and "
        "opening a pull request on an issue nobody wants",
        gate.spec.slug, gate.issue.number, generation.cycle_id,
    )
    _marked(gate, generation)
    return True


def _marked(gate: _records._Gate, generation: LateGeneration) -> None:
    """Record this cycle cancelled, then report it, in that order.

    Nothing is owed a publication on a cancelled cycle, so the commit an
    approval had recorded goes with it -- including one this very call is
    reinstating a generation over. Left standing it would freeze the branch
    out of the base refresh for as long as the issue lives and park a later
    tick asking for a checkout back for work nobody is going to push.
    """
    cancelled = replace(
        generation.cancel(_usage._now_iso()),
        phase=LatePhase.CANCELLING,
        owner_check_pending=False,
    )
    gate.state.set(_state._APPROVED_SHA, None)
    _late_state.write_late_generation(gate.state, cancelled)
    _late_state.clear_retired_cycle(gate.state)
    gate.gh.write_pinned_state(gate.issue, gate.state)
    _parks._emit(
        gate, cancelled,
        _events.LateEvent(family=_events.LateEventFamily.CANCELLATION),
    )


def _routed(gate: _records._Gate, generation: LateGeneration) -> bool:
    """Hand an oversized candidate to the adjudication, publishing nothing.

    The measurement is made durable first, because the label is what makes
    another handler read this issue: a tick that dies between the two leaves a
    live oversized generation under `workflow:implementing`, which the
    dispatcher's own relabel guard puts back where the adjudication left it.
    The reverse order would hand the coordinator an issue whose record cannot
    say what is being adjudicated.

    Nothing is pushed and no pull request is opened. The commit stays in the
    developer's worktree, which is where the adjudicator reads it and where a
    `single` verdict publishes it from.
    """
    log.warning(
        "issue=#%d candidate %s adds %d lines against a ceiling of %d; "
        "holding it unpublished and routing it to %s",
        gate.issue.number, generation.candidate_sha, generation.additions,
        generation.threshold, WorkflowLabel.DECOMPOSING,
    )
    # Whatever commit this issue was owed a publication for, it is not owed
    # one now: the branch carries a candidate under adjudication, and the
    # record naming it is what the coordinator reconciles from here. Left
    # standing, an approval this candidate was committed on top of would hold
    # the branch out of the base refresh for the whole adjudication and park
    # every later tick on a host that no longer has that commit.
    gate.state.set(_state._APPROVED_SHA, None)
    _parks._persisted(gate, generation)
    _comments._post_issue_comment(
        gate.gh, gate.issue, gate.state,
        _ROUTED_NOTICE.format(
            additions=generation.additions,
            threshold=generation.threshold,
            candidate=generation.candidate_sha,
            label=WorkflowLabel.DECOMPOSING,
        ),
    )
    gate.gh.write_pinned_state(gate.issue, gate.state)
    gate.gh.set_workflow_label(gate.issue, WorkflowLabel.DECOMPOSING)
    return True
