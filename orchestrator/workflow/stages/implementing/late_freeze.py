# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The pair a count is taken over, and what a record has to carry to be one.

Which commit this tick is deciding about, which base it is measured against,
and whether a record already answering that question may be acted on. Every
answer here is a claim about one object id -- proved in the checkout, or
recorded and proved again -- because a measurement is only worth as much as
the two commits it names, and as much as the identity it can be correlated
by afterwards.
"""
from __future__ import annotations

import logging
from typing import Optional

from orchestrator import config
from orchestrator.git.measurement import commits as _measurement_commits
from orchestrator.git.measurement.models import (
    FrozenCommit,
    MeasurementFailure,
)
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.implementing import (
    late_parks as _parks,
    late_records as _records,
)

log = logging.getLogger("orchestrator.workflow")

_HEAD = "HEAD"

_MEASUREMENT_FIELDS = (
    ("late_base_sha", lambda recorded: not recorded.base_sha),
    ("late_threshold", lambda recorded: recorded.threshold is None),
    ("late_phase", lambda recorded: recorded.phase is None),
)

_MISSING_FIELD = "`{field}` is missing from it"

_DAMAGED_RECORD_PARK = (
    "{mentions} this issue records a measurement of `{candidate}` that "
    "cannot be acted on: {damaged}. A count with no ceiling beside it is not "
    "a verdict and a count recorded against another issue is not this one's "
    "answer, so reading either as a small candidate would publish an "
    "implementation nobody measured. Nothing was published and nothing was "
    "re-run. Repair the pinned comment, or commit again so the candidate is "
    "measured afresh, and reply `/orchestrator continue`."
)

def _candidate_commit(
    gate: _records._Gate, recorded: LateGeneration,
) -> Optional[FrozenCommit]:
    """The commit this tick decides about, or None when the gate is off for it.

    `DECOMPOSE=off` is a decision about NEW work: it stops a candidate ever
    entering the gate and deliberately decides nothing about one already in
    it. So the switch is read against the record rather than on its own, and
    an issue with nothing recorded is the only one it answers outright -- for
    which no commit is proved at all, since there is no question to prove one
    for.

    A RECONCILIATION is never that issue, whatever the record says. It is a
    reading a previous tick recorded an intent to take -- a park a human
    answered, a frozen pair a crash stranded -- and the commonest way to reach
    one with no candidate recorded is the refusal that happens before a
    generation can be minted: the candidate could not be proved, so there was
    nothing to freeze. Reading that as new work is the switch failing OPEN,
    publishing the very head whose reading is what somebody asked for. The
    switch keeps new candidates out of the gate; it does not answer a question
    the gate already asked.

    An issue that still OWES a push is never that issue either, and for the
    same reason one step later: the gate approved a commit, the record naming
    it was dropped by the write that approved it, and the push has not
    happened. Bypassing there hands the publication a candidate this gate has
    not looked at while the record beside it says a debt was paid -- and the
    debt is for one commit and only it, so what would ship is a head under a
    decision taken about a different one.

    The commit is proved rather than read, because everything downstream is a
    claim about one object id: a revision this host cannot peel to a commit is
    work made somewhere else, and nothing here may stand the current head in
    for it.
    """
    if not config.DECOMPOSE and not recorded.candidate_sha:
        if not gate.reconciling and not _parks._approved_commit(gate.state):
            return None
    head = _measurement_commits._prove_candidate_commit(gate.worktree, _HEAD)
    if not recorded.candidate_sha:
        return head
    if head.is_frozen and head.sha == recorded.candidate_sha:
        return head
    return _reconciled_candidate(gate, recorded, head)


def _reconciled_candidate(
    gate: _records._Gate, recorded: LateGeneration, head: FrozenCommit,
) -> Optional[FrozenCommit]:
    """What a record whose candidate is not the current head is reconciled as.

    The recorded commit is asked for FIRST, and that order is the whole
    contract: a recorded SHA is the evidence, and the current head is never a
    substitute for it. A host that cannot peel that object is one the work was
    not made on -- a rebuilt checkout, a machine the branch never reached --
    and it parks rather than measuring, adjudicating, or publishing whatever
    the branch happens to point at there.

    Past that proof the two commits are both HERE, and what that means splits
    on whether a developer ran. On an ordinary disposition it is the ordinary
    situation: the developer was resumed on a human's guidance and committed
    again, so the branch has genuinely moved past what was frozen. That is a
    fresh candidate, measured under a fresh generation of the same cycle --
    exactly as a revision under the adjudication label is. With the switch off
    it is a fresh candidate the gate does not measure, and the record it
    supersedes is retired rather than left standing: a `late_candidate_sha`
    naming work no longer on the branch freezes this branch out of the base
    refresh for good, and describes a commit nothing is going to publish.

    On a RECONCILIATION none of that is available, and the checkout having
    been on the recorded commit a moment ago does not make it available. No
    developer ran on this tick, so there is no run whose output a moved head
    could be; the paths that reach here proved the head against the record
    before they started, and a head that differs NOW is one something moved
    while the tick was in flight -- another process, an operator, a descendant
    the timeout cleanup raced. Reading it as fresh work would measure and
    publish a commit this reconciliation was never about, and with the switch
    off it would retire the record and push that head unmeasured. So the
    reading is refused and the recorded pair is left standing for the retry,
    which is the same answer the pre-gate proof gives to a head that had
    already moved.

    That refusal is asked BEFORE the head is asked whether it is readable, and
    the order is the point: a head that moved to a commit this host cannot
    peel still NAMES one, and a named commit handed back from here is one the
    park downstream records -- minting a generation around it and dropping the
    pair this reconciliation exists to re-read. Unreadable or not, a head that
    is not the recorded candidate is not this tick's to substitute, so on a
    reconciliation it is refused without a name rather than passed on with
    one.
    """
    kept = _measurement_commits._prove_candidate_commit(
        gate.worktree, recorded.candidate_sha,
    )
    if not kept.is_frozen:
        log.error(
            "issue=#%d records candidate %s, which this host cannot read; "
            "refusing to reconcile it against HEAD instead",
            gate.issue.number, recorded.candidate_sha,
        )
        return kept
    if gate.reconciling:
        log.error(
            "issue=#%d is reconciling recorded candidate %s and its checkout "
            "moved to %s mid-tick; refusing to read a head no run of this "
            "tick produced as fresh work",
            gate.issue.number, recorded.candidate_sha,
            head.sha or head.failure,
        )
        return FrozenCommit(
            failure=MeasurementFailure.CANDIDATE_UNREADABLE,
        )
    if not head.is_frozen:
        return head
    return head if config.DECOMPOSE else None


def _already_measured(recorded: LateGeneration, candidate_sha: str) -> bool:
    """Whether the record already answers the size question for this commit."""
    return (
        recorded.candidate_sha == candidate_sha
        and recorded.additions is not None
    )


def _frozen_pair(
    gate: _records._Gate, recorded: LateGeneration, candidate_sha: str,
) -> Optional[LateGeneration]:
    """Persist the exact pair a count is taken over, or park without one.

    The write is the point of the step. It goes out BEFORE the count, carrying
    both commits and the `measuring` boundary, so a tick that dies over the
    diff comes back to the pair this one froze rather than re-deriving one
    from a branch and a remote that have both moved -- which is the difference
    between a retry that measures the same candidate and a retry that measures
    a different one.

    A pair this issue already froze for the commit in hand is reused as it
    stands, and the remote is not asked again. It is the same evidence, the
    base it names is the one a verdict has to be defensible against, and
    re-freezing would let a base that advanced between two ticks change the
    size of a candidate nobody touched -- which is exactly what a retry after
    a base this host could not read would otherwise do, since the id it failed
    on is recorded and the branch it came from has moved on since.

    So the reuse proves that recorded object rather than assuming it, fetching
    once for it as the freeze itself does. It is the retry the recorded
    identity exists for: the SAME commit is asked for again, and a host that
    still does not have it parks rather than measuring against a base nobody
    froze.

    None is a base the remote would not name, or one this host does not hold,
    which is a measurement that did not happen. The identity is recorded all
    the same -- beside the failure, where the freeze puts it -- so the failure
    is reportable on both sinks and the retry has one exact object to ask for.
    """
    if recorded.candidate_sha == candidate_sha and recorded.base_sha:
        if _damaged_record(gate, recorded):
            return None
        return _refrozen_base(gate, recorded)
    base = _measurement_commits._freeze_base_commit(gate.spec, gate.worktree)
    minted = _records._minted(gate, recorded, candidate_sha, base.sha)
    _parks._persisted(gate, minted)
    if base.is_frozen:
        return minted
    _parks._unmeasured(gate, minted, base.failure)
    return None


def _refrozen_base(
    gate: _records._Gate, recorded: LateGeneration,
) -> Optional[LateGeneration]:
    """Prove the recorded base is readable here, or park without re-reading it.

    The one question a reused pair still has to ask, because the pair is
    durable and the object store is not: a record written on one host and
    retried on another -- or on the same host after a prune -- names a commit
    this checkout may not hold. Asking the REMOTE again instead would answer
    with wherever the base branch is now, so the retry a human's continue
    drives would silently measure a different pair under the same generation.
    """
    if _measurement_commits._base_object_present(
        gate.spec, gate.worktree, recorded.base_sha,
    ):
        return recorded
    log.error(
        "issue=#%d records base %s, which this host does not hold even after "
        "a fetch; refusing to re-read the remote for a different one",
        gate.issue.number, recorded.base_sha,
    )
    _parks._unmeasured(
        gate, _records._reportable(gate, recorded),
        MeasurementFailure.BASE_ABSENT,
    )
    return None


def _incomplete_measurement(
    gate: _records._Gate, recorded: LateGeneration,
) -> Optional[str]:
    """Why a recorded measurement may not be acted on, or None if it may.

    Named rather than counted, because the park has to tell a human which
    part to repair -- and because the parts are not interchangeable: a missing
    threshold and a missing base are two different reasons the number beside
    them means nothing.

    The identity carries the same weight as the count's own fields and is the
    half that is easy to forget, because nothing downstream reads it: a record
    with no cycle, no generation, or no root cannot be joined to the audit
    line the measurement was reported on, to the lineage a split would be
    bounded by, or to the verdict an adjudication files -- and a count that
    can be published but not correlated is a reading no operator can defend
    afterwards. One naming another issue is worse still: it is not this
    issue's answer at all, so publishing on it would ship work here on a
    reading taken over there.
    """
    for field, missing in _MEASUREMENT_FIELDS:
        if missing(recorded):
            return _MISSING_FIELD.format(field=field)
    return _records._unusable_identity(gate, recorded)


def _damaged_record(gate: _records._Gate, recorded: LateGeneration) -> bool:
    """Park a recorded pair whose metadata cannot be acted on, or pass it.

    Asked on BOTH roads into a recorded pair, because the fields it checks are
    written by the freeze rather than by the count: a record reused for a
    reading that has still to be taken is as damaged without them as one whose
    number is already in. The counted road would otherwise be the only one
    guarded, and the uncounted one -- the ordinary crash retry -- would carry
    a threshold-less record into `_verdict_owner._settled`, where the record's own comparison
    answers "not oversized" on a missing ceiling and publishes it.

    The failure reaches both sinks like every other refusal, so a record that
    fails open in the log is not what an operator has to notice.
    """
    damaged = _incomplete_measurement(gate, recorded)
    if damaged is None:
        return False
    log.error(
        "issue=#%d records a measurement of %s that cannot be acted on "
        "(%s); parking rather than reading it as an answer",
        gate.issue.number, recorded.candidate_sha, damaged,
    )
    return _parks._parked(
        gate, _records._reportable(gate, recorded), damaged,
        _DAMAGED_RECORD_PARK.format(
            mentions=config.HITL_MENTIONS,
            candidate=recorded.candidate_sha,
            damaged=damaged,
        ),
    )
