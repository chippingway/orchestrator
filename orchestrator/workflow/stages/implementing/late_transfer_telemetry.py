# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a settled transfer says on the streams, once it is durable.

The observability half of the far end of the transfer. `late_rotation` decides
what a landed publication does to the permission that licensed it -- spend it,
drop it, or leave it standing -- and this owner says what the stream is told
once that decision is on the comment. Split because they answer to different
readers: the decision is a claim about the pinned state, held to the permit and
to the rollback's rule, while the record is a claim about work that moved, held
to a field list two sinks and every query over them are written against.

Reached from the push tail rather than from the rotation, and only on the far
side of the pinned write it stages, which is what makes the order a property of
the call site rather than an instruction one owner is trusted to honour. A
record of a verdict that moved is worth nothing if the write carrying the move
was refused -- and a refused write ends the tick, so there is no road on which
the transfer stands reported and unsettled.

One record, and one family. A transfer carries a decision a human already made
onto the object that replaced the one they made it about, so a second
`late_verdict` on the stream would read as a second adjudication of work nobody
was asked about twice -- and a rotation that moved no verdict says nothing at
all, because a permission left standing and one this publication went past
both leave the exemption exactly where the adjudication put it.
"""
from __future__ import annotations

from dataclasses import replace

from orchestrator.workflow.late_split import (
    events as _events,
    rewrites as _rewrites,
    state as _late_state,
    telemetry as _telemetry,
)
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.implementing import (
    late_records as _records,
    late_rotation as _rotation,
)


def _reports_the_transfer(
    gate: _records._Gate, rotation: _rotation._Rotation,
) -> None:
    """Write the one record a settled transfer leaves on both sinks.

    Reported once the move is durable rather than beside it, because a record
    of a verdict that moved is worth nothing if the write carrying the move
    was refused -- and a refused write ends this tick, so there is no road on
    which the transfer stands unreported.

    The pair the record carries is the pair the exemption moved ONTO, since
    that is what a later measurement of this same work would be joined on, and
    the publication group comes off the AUTHORIZATION rather than off the
    caller: the record is the account of the pull request the transfer was
    granted against, and the caller in the push tail has no entry of its own
    to read one from. The source stage rides the same record for the same
    reason -- the rewrite names the stage it was entered from, which a tail
    reached from anywhere cannot re-derive.

    Silent where nothing moved, which is both roads the rotation stages
    without a rewrite behind it: a permission no permit vouched for and one
    the publication went past each leave the exemption where the adjudication
    put it, and a stream told about them would be describing a transfer that
    did not happen.
    """
    if not rotation.is_reportable:
        return
    rewrite = rotation.rewrite
    _telemetry.emit_late_event(
        gate.gh,
        _events.LateEvent(
            family=_events.LateEventFamily.TRANSFER,
            rewrite_kind=rewrite.kind,
            transfer_proof=rotation.proof,
            transferred_from_sha=rewrite.from_sha,
            transferred_from_base_sha=rewrite.from_base_sha,
        ),
        _reported(gate, rewrite),
        stage=rewrite.source_stage,
    )


def _reported(
    gate: _records._Gate, rewrite: _rewrites.LateRewrite,
) -> LateGeneration:
    """The generation one transfer record is correlated by.

    Minted the way every other record with no live generation behind it is: a
    transfer runs past the retirement that dropped the pair it was adjudicated
    under, so there is no cycle left to file it against and one is derived
    from what the pinned comment already says. Stable across retries, so a
    settlement that lands twice reports the same attempt rather than a fresh
    one each tick.

    No phase, and deliberately: the phases are the boundaries a generation's
    reconciliation stands at, and a transfer is not one of them -- it happens
    past the retirement that ended the last.
    """
    recorded = _late_state.read_late_generation(gate.state)
    carried = replace(
        _records._reportable(gate, recorded),
        candidate_sha=rewrite.to_sha,
        base_sha=rewrite.to_base_sha,
        phase=None,
    )
    return carried.with_publication(
        stage=rewrite.source_stage,
        pr_number=rewrite.pr_number,
        published_sha=rewrite.lease,
    )
