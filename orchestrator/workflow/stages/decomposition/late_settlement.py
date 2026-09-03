# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a guarded verdict earns, once the owner has been read again.

The step between `late_outcome`, which decides what a reply MEANS, and the
transactions that act on it. Nothing reaches those transactions except through
here, and nothing reaches here without a fresh owner read behind it: the
coordinator takes that read on every completed run and only calls this owner
when it came back open, so every branch below may assume the issue is still
there.

The announcement a question owes the issue is made here rather than where the
question was recorded, and that is the whole reason it moved: the record has
to go out before anything is said, and the owner read has to go out between
them, so a question is not posted to a thread somebody closed while the agent
was still answering it. It is the only external effect a question earns --
no publication, no snapshot, no supersession, no activation.

A `split` is handed on rather than acted on. Creating children, taking the
snapshot they are cut from, and superseding the pull request its work is on are
one transaction and belong together; what this owner owes it is the guarantee
it cannot check for itself -- that the outcome it is given was re-checked
against an owner read taken after the agent finished.

A `single` is reconciled here, and this owner keeps the ORDER of that
reconciliation while the steps themselves are owned beside it: `late_reconcile`
takes the hold off and settles which pull request the issue records,
`late_verdict_push` makes the push a candidate measured past publication
earns, and `late_handback` hands the label on and retires the cycle.

Every one of them earns an EXEMPTION: a durable record that this exact commit
has been adjudicated, or the gate would measure the same candidate past the
same ceiling and adjudicate it again forever. The exemption names the measured
commit and only it -- work committed after the verdict is work nobody
adjudicated, and the gate measures it as the fresh candidate it is.

A candidate nothing had published earns only that. It is already committed in
the developer's own worktree, and the ordinary `implementing` publication the
issue is handed back to is what pushes it, opens or reuses its pull request,
and hands it to review. A candidate measured against a pull request the remote
ALREADY carries earns the push as well, and the stage it is handed back to is
the one the record names rather than `implementing`.

Never a snapshot. A snapshot exists so children can be cut from a candidate
that is about to be superseded, and an accepted candidate is superseded by
nothing -- it publishes as itself, from the branch it is already on.

The order is chosen so every window a crash can land in is one the next tick
repairs. The hold is released first, while nothing else has moved. The
exemption is written next -- with the commit a push is still owed for beside
it -- and the generation is still live behind them, so the issue is still an
adjudication in flight. Then the push, then the label, and only after that is
the generation cleared: a `decomposing` issue with no generation on it is one
the INITIAL decomposer would pick up and re-decompose, and an issue back on
its own stage with a live generation is one the relabel guard puts back and
this tick re-settles.
"""
from __future__ import annotations

import logging
from dataclasses import replace

from orchestrator.workflow.late_split import exemption as _exemption
from orchestrator.workflow.late_split.models import LateVerdict
from orchestrator.workflow.stages.decomposition import (
    late_handback as _late_handback,
    late_outcome as _late_outcome,
    late_owner as _late_owner,
    late_parks as _late_parks,
    late_reconcile as _late_reconcile,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    _GuardedSplit,
    _LateAdjudicationRun,
    _LateContext,
    _LateDisposition,
)
from orchestrator.workflow.stages.implementing import late_parks as _gate_parks

log = logging.getLogger("orchestrator.workflow")


def _settle_adjudication(
    context: _LateContext, finished: _LateAdjudicationRun,
) -> _LateAdjudicationRun:
    """Act on what one guarded run left, if it left a verdict at all.

    A completion that decided nothing -- a timeout, an unusable reply, an
    outcome too large to record -- has already parked itself and reaches here
    only so the owner read in front of it was taken. There is nothing to
    settle, and it is handed straight back.

    The result of one that DID decide is already durable by the time this
    runs; that is `late_outcome`'s contract, and it is what makes the
    fail-closed read in front of this affordable: a tick that stops there has
    lost a GitHub read and not an agent run.
    """
    adjudication = finished.adjudication
    if finished.disposition != _LateDisposition.DECIDED or adjudication is None:
        return finished
    if adjudication.verdict == LateVerdict.QUESTION:
        _late_outcome._announce(context, adjudication)
        return finished
    if adjudication.verdict == LateVerdict.SPLIT:
        return _handed_split(context, finished)
    return _reconcile_single(context, finished)


def _handed_split(
    context: _LateContext, finished: _LateAdjudicationRun,
) -> _LateAdjudicationRun:
    """Report a split the owner read cleared, for the transaction to take.

    Nothing is created, snapshotted, or superseded here. What travels is the
    generation as the guard left it and the manifest the verdict decided on,
    so the transaction acts on the exact answer that was guarded rather than
    re-reading a pinned comment that has moved on since.
    """
    log.info(
        "issue=#%d late generation %d split into %d children is cleared to "
        "run: its owner was open when the adjudication finished",
        context.issue.number,
        context.generation.generation,
        len(finished.adjudication.children),
    )
    return replace(
        finished,
        generation=context.generation,
        guarded_split=_GuardedSplit(
            generation=context.generation,
            children=finished.adjudication.children,
        ),
    )


def _reconcile_single(
    context: _LateContext, finished: _LateAdjudicationRun,
) -> _LateAdjudicationRun:
    """Exempt exactly the measured commit and hand the candidate back.

    Two reconciliations first, and the second is the one a search by branch and
    open state cannot make: the hold comes off the pull request it marked, and
    the pull request this issue RECORDS is settled against the measured commit,
    so what the handoff names is a change the accepted candidate is actually
    in. Everything durable goes out in one write ahead of the label that hands
    it on, since the label is what makes another stage read it.

    Never a snapshot. A snapshot is what children are cut from when the
    candidate they came out of is about to be superseded, and an accepted
    candidate supersedes nothing: it publishes as itself, from the branch it
    is already committed on, so preserving a copy of it would create an
    obligation with nothing on the other end.

    The owner is asked between every one of the steps that follow, and these
    are the barriers in this mode that protect the RECORD rather than an
    effect: the last write drops the cycle entirely, and the sweep that should
    end a cancelled one reads that cycle to decide anything is owed. So a close
    latched during the hold release, the pull-request lookup, the exemption
    write, or the handoff label stops here -- not one step later, where the
    generation the durable receipt would be adopted against no longer exists.

    Latch-only, like the create and the spawn: the claim a full guard writes
    would name `owner_check` over the boundary this tick reached.
    """
    reconciled = (
        _late_reconcile._released_hold(context)
        and _late_reconcile._reconciled_pr(context)
    )
    if not reconciled:
        return _late_outcome._finished(context, _LateDisposition.PARKED)
    ended = _handed_back(context)
    if ended is not None:
        return _late_outcome._finished(context, ended)
    return replace(
        finished,
        disposition=_LateDisposition.SETTLED,
        generation=context.generation,
    )


def _handed_back(context: _LateContext) -> _LateDisposition | None:
    """Record the exemption, hand the label on, and retire the cycle.

    Three requests in the one order a crash in them is safe in, with the
    latch asked between each: the exemption is what stops the gate measuring
    the same commit again, the label is what makes another stage read it, and
    the retirement is what says this issue has no late question left. None is
    reached over a close somebody observed.

    The exemption is joined by the commit the handoff is owed a publication
    for, and the pair is what makes the retirement behind them survivable. An
    exemption says a commit needs no measuring; it does not say the issue is
    still waiting for it to be pushed, and past the retirement the generation
    that did say so is gone. A tick that died in that window would leave an
    `implementing` issue whose branch carries an adjudicated commit and whose
    record names none, so a replacement host -- rebuilding the checkout from
    the base or the plan pull request -- would publish that head or spawn a
    second developer over an implementation a human has already ruled on.
    Recorded, the implementing gate proves the commit before anything runs and
    parks for the checkout instead.
    """
    stopped = _late_owner._latch_stops(context)
    if stopped is not None:
        return stopped
    _exemption.record_exemption(
        context.state, context.generation.candidate_sha,
    )
    _recorded_debt(context)
    _late_parks._persist(context)
    stopped = _late_owner._latch_stops(context)
    if stopped is not None:
        return stopped
    return _late_handback._continued(context)


def _recorded_debt(context: _LateContext) -> None:
    """Record the push this handoff owes, or drop one already paid.

    The approval says a commit is owed a publication and no other may be
    pushed in its place, which is exactly what a retry finishing an
    interrupted settlement does NOT owe: the pull request is already standing
    on that commit. Recording it there would leave a debt nothing will ever
    pay -- the push is skipped -- and a debt on the record freezes this
    branch out of the pre-tick base refresh for the rest of the issue's life.
    """
    if context.already_published:
        _gate_parks._forget_approval(context.state)
        return
    _gate_parks._approve(
        context.state,
        context.generation.candidate_sha,
        _settled_lease(context),
    )


def _settled_lease(context: _LateContext) -> str:
    """The head the publication this verdict was taken over is pinned to.

    The retirement takes the generation -- and the head it froze -- off the
    record, and the push the handoff licenses runs in another stage entirely.
    Without this the publication would read the remote for itself, which is
    right for a candidate nothing has published and wrong for one adjudicated
    against a pull request that already exists: between the proof a moment ago
    and the push, that pull request can move, and an unpinned force-push adopts
    whoever landed as the lease.

    Empty for a pre-publication verdict, whose push has no pull request to be
    pinned to and correctly takes its own reading.
    """
    if not context.generation.has_publication_context:
        return ""
    return context.generation.published_sha
