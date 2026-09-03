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

A `single` is reconciled here, and what that means splits on which side of
publication the candidate was measured on.

Every one of them earns an EXEMPTION: a durable record that this exact commit
has been adjudicated, or the gate would measure the same candidate past the
same ceiling and adjudicate it again forever. The exemption names the measured
commit and only it -- work committed after the verdict is work nobody
adjudicated, and the gate measures it as the fresh candidate it is.

A candidate nothing had published earns only that. It is already committed in
the developer's own worktree, and the ordinary `implementing` publication the
issue is handed back to is what pushes it, opens or reuses its pull request,
and hands it to review.

A candidate measured against a pull request the remote ALREADY carries earns
the push as well, and this owner makes it. Only this tick still holds the
evidence: the verdict was taken against one pull request standing on one head,
the reconciliation above proves both are still what they were, and the
retirement below takes the record that said so away. The stage the issue is
then handed back to -- the one the record names, not `implementing` -- has its
own completion to finish and no way to re-derive any of that, and two of the
five have no publication seam a resumed tick would even reach. So the branch
is put where the verdict said it may go, named against the accepted commit and
pinned to the head the reading was taken over, and the stage picks up from a
pull request that carries it.

Two things it deliberately does not do. It creates no snapshot: a snapshot
exists so children can be cut from a candidate that is about to be superseded,
and an accepted candidate is superseded by nothing -- it publishes as itself,
from the branch it is already on. And it restores rather than rewrites: the
held pull request gets back the description this generation replaced, and what
happens to that pull request afterwards is the ordinary reconciliation's --
the publication that follows reuses it and rewrites its body when the push
lands on it, and leaves it alone when it does not.

The order is chosen so every window a crash can land in is one the next tick
repairs. The hold is released first, while nothing else has moved. The
exemption is written next -- with the commit a push is still owed for beside
it -- and the generation is still live behind them, so the issue is still an
adjudication in flight. Then the push, then the label, and only after that is
the generation cleared: a `decomposing` issue with no generation on it is one
the INITIAL decomposer would pick up and re-decompose, and an issue back on
its own stage with a live generation is one the relabel guard puts back and
this tick re-settles.

The window between the push and the label is the one the record alone cannot
answer, and it has its own recognition. The retry comes back to a live
generation whose pull request is standing on the accepted candidate rather
than on the frozen head -- which is this settlement's own push, not somebody
else's movement. Read as movement it would refuse the very publication this
verdict made, forever; recognized, the tick finishes the label and the
retirement it never reached and pushes nothing a second time.
"""
from __future__ import annotations

import logging
from dataclasses import replace

from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.github import pull_requests as _pull_requests
from orchestrator.workflow.engine import comments as _comments, observations as _observations
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    formats as _formats,
    payloads as _payloads,
    state as _late_state,
)
from orchestrator.workflow.late_split.models import (
    LateFailure,
    LateGeneration,
    LateVerdict,
)
from orchestrator.workflow.stages.decomposition import (
    late_hold as _late_hold,
    late_outcome as _late_outcome,
    late_owner as _late_owner,
    late_parks as _late_parks,
    late_publication as _late_publication,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    _GuardedSplit,
    _LateAdjudicationRun,
    _LateContext,
    _LateDisposition,
)
from orchestrator.workflow.stages.implementing import (
    late_accepted as _late_accepted,
    late_parks as _gate_parks,
    late_records as _late_records,
)
from orchestrator.workflow.state import WorkflowLabel

log = logging.getLogger("orchestrator.workflow")

# Whichever pull request this issue currently records, and the one state in
# which keeping it is safe. Shared with every other stage that reads it, which
# is why what it names has to be true by the time this hands the issue on.
_PR_NUMBER = "pr_number"

_OPEN_PR_STATE = "open"

_RELEASE_FAILED_PARK = (
    "this issue's committed candidate was adjudicated as one coherent change, "
    "but the hold on its pull request could not be taken off -- so nothing "
    "was handed on for publication and the pull request still reads as held. "
    "Settle the pull request, then the next tick retries the same release "
    "against the same recorded description."
)

_LOOKUP_FAILED_PARK = (
    "this issue's committed candidate was adjudicated as one coherent change, "
    "but GitHub could not be asked which pull request already carries it -- "
    "so it was not handed on for publication. Publishing on that answer could "
    "open a second pull request for a commit that is already on one. The next "
    "tick asks again, against the same frozen commit, without re-running any "
    "agent."
)

_RECORDED_PR_UNREADABLE_PARK = (
    "this issue's committed candidate was adjudicated as one coherent change, "
    "but the pull request this issue records could not be read -- so it was "
    "not handed on for publication. A merged one carried into the "
    "implementing stage ends the issue on a change the candidate is not in. "
    "The next tick asks again, against the same frozen commit, without "
    "re-running any agent."
)

_SETTLED_PUBLICATION_PARK = (
    "this issue's committed candidate was adjudicated as one coherent change, "
    "but pull request #{number} -- the one it was measured against -- is "
    "{state} rather than open, so it was not handed on for publication. The "
    "reading that accepted it is a claim about what THAT pull request would "
    "come to, and there is nowhere for the commit to land any more: pushing "
    "would grow a branch whose pull request a human has already settled, or "
    "open a second one for a change that was adjudicated against the first. "
    "Reopen it, or close this issue, and the next tick asks again."
)

_MOVED_PUBLICATION_PARK = (
    "this issue's committed candidate was adjudicated as one coherent change "
    "against pull request #{number} standing at `{frozen}`, and it is "
    "standing at `{moved}` now. Something pushed to it during the "
    "adjudication, so what the verdict was taken over is not what the branch "
    "would come to -- and it was not handed on for publication. Reconcile the "
    "branch with what landed, then commit again so the candidate is measured "
    "afresh."
)

_ACCEPTED_PUSH_FAILED_PARK = (
    "this issue's committed candidate was adjudicated as one coherent change, "
    "but it could not be pushed onto the pull request it was measured against "
    "-- so the issue is still under adjudication and nothing has moved. The "
    "verdict is recorded: the next tick pushes the same commit against the "
    "same head, without re-running any agent. A push refused here is usually "
    "the lease doing its job, which means something landed on that pull "
    "request while the adjudication was open."
)

_UNPROVED_CHECKOUT_PARK = (
    "this issue's committed candidate was adjudicated as one coherent change "
    "and `{candidate}` is on the pull request it was measured against, but "
    "the checkout it was accepted from is not standing cleanly on that commit "
    "any more -- so the issue is still under adjudication and the stage it "
    "came from has not been handed the worktree. Every stage past this one "
    "works from that checkout, so one carrying loose edits or an unmeasured "
    "descendant would reach a review, a squash, and a merge with nobody "
    "having read it. Put the worktree back on that commit with a clean "
    "tree and the next tick finishes the settlement, without re-running any "
    "agent."
)

_ACCEPTED_NOTICE = (
    ":white_check_mark: the late decomposer read the committed candidate "
    "`{candidate}` as one coherent change ({additions} added lines against a "
    "ceiling of {threshold}), so it publishes as it stands. Only that commit "
    "is exempt -- anything committed on top of it is measured again."
)


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

    Two reconciliations, and the second is the one a search by branch and open
    state cannot make: the hold comes off the pull request it marked, and the
    pull request this issue RECORDS is settled against the measured commit, so
    what the handoff names is a change the accepted candidate is actually in.
    Everything durable goes out in one write ahead of the label that hands it
    on, since the label is what makes another stage read it.

    Never a snapshot. A snapshot is what children are cut from when the
    candidate they came out of is about to be superseded, and an accepted
    candidate supersedes nothing: it publishes as itself, from the branch it
    is already committed on, so preserving a copy of it would create an
    obligation with nothing on the other end.

    The owner is asked between every one of the steps below, and these are
    the barriers in this mode that protect the RECORD rather than an effect:
    the last write drops the cycle entirely, and the sweep that should end a
    cancelled one reads that cycle to decide anything is owed. So a close
    latched during the hold release, the pull-request lookup, the exemption
    write, or the handoff label stops here -- not one step later, where the
    generation the durable receipt would be adopted against no longer exists.

    Latch-only, like the create and the spawn: the claim a full guard writes
    would name `owner_check` over the boundary this tick reached.
    """
    if not _released_hold(context) or not _reconciled_pr(context):
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
    return _continued(context)


def _recorded_debt(context: _LateContext) -> None:
    """Record the push this handoff owes, or drop one already paid.

    The approval says a commit is owed a publication and no other may be
    pushed in its place, which is exactly what a retry finishing an
    interrupted settlement does NOT owe: the pull request is already standing
    on that commit. Recording it there would leave a debt nothing will ever
    pay -- the push below is skipped -- and a debt on the record freezes this
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


def _continued(context: _LateContext) -> _LateDisposition | None:
    """Publish where the verdict was measured, then hand the label on.

    Split from the exemption above it so each half is one crash-ordered
    sequence rather than one long one: what is durable before this call is the
    decision, and what this call does is the effects the decision licenses.
    """
    if not _pushed_where_it_was_measured(context):
        return _LateDisposition.PARKED
    stopped = _late_owner._latch_stops(context)
    if stopped is not None:
        return stopped
    context.gh.set_workflow_label(context.issue, _continues_at(context))
    stopped = _late_owner._latch_stops(context)
    if stopped is not None:
        return stopped
    return _published(context)


def _continues_at(context: _LateContext) -> WorkflowLabel:
    """The state a settled adjudication puts this issue back into.

    The record's own answer where it has one. A generation entered on the
    published side names the stage the gate took the issue out of, and that
    stage is the only one whose completion the candidate still owes: a docs
    commit owes the watermark, the notice, and the `in_review` handoff; a
    conflict resolution owes its round; a fix owes the reviewer another look.
    Sending every one of them to `implementing` instead publishes the commit
    and then walks the issue back to a point in the pipeline it had already
    passed, skipping the bookkeeping the stage it came from is the only owner
    of.

    `implementing` is the answer for a candidate nothing had published, which
    is the only other kind: there is no other stage it could have come from.
    """
    if not context.generation.has_publication_context:
        return WorkflowLabel.IMPLEMENTING
    return context.generation.source_stage


def _pushed_where_it_was_measured(context: _LateContext) -> bool:
    """Put an accepted post-publication candidate on its pull request.

    The push belongs HERE rather than to the stage the issue continues at,
    and the reason is that only this tick still holds the evidence. The
    verdict was taken against one pull request standing on one head; the
    reconciliation a moment ago proved both are still what they were; and the
    retirement below takes the record that said so away. The stage resumed
    behind this one has its own work to finish and no way to re-derive any of
    that -- and two of the five have no publication seam a resumed tick would
    even reach.

    So the branch is put where the verdict said it may go, and the stage picks
    up from a pull request that carries the commit. A push that did not land
    parks with the label still on the adjudication: the exemption and the
    approval are already durable, so the retry asks for the same commit
    against the same head and settles from there.

    A pre-publication verdict pushes nothing here. Its candidate has no pull
    request yet, and the `implementing` publication it is handed back to is
    what opens one. Neither does a retry finishing a settlement whose push
    already landed: the reconciliation above found the pull request standing
    on the accepted candidate, so what is left to finish is the label and the
    retirement, not a second push of a commit that is already there.

    Both of those still owe the checkout, which is why the proof below is on
    the road out rather than inside the push: what the verdict licensed is one
    commit, and the worktree it was accepted from is writable through the
    whole adjudication, through the push itself, and through the tick that
    died between a landed push and this retry.
    """
    if not context.generation.has_publication_context:
        return True
    worktree = _worktree_paths._worktree_path(
        context.spec, context.issue.number,
    )
    if not context.already_published and not _accepted_push_landed(
        context, worktree,
    ):
        return False
    return _proved_before_the_handoff(context, worktree)


def _accepted_push_landed(context: _LateContext, worktree) -> bool:
    """Put the accepted commit on its pull request, or park for the retry.

    A push that did not land leaves the label on the adjudication: the
    exemption and the approval are already durable, so the retry asks for the
    same commit against the same head and settles from there.
    """
    if worktree.exists() and _late_accepted._publishes_approved(
        _late_records._gate(
            context.gh, context.spec, context.issue, context.state, worktree,
        ),
        _worktree_paths._resolve_branch_name(
            context.state, context.spec, context.issue.number,
        ),
    ):
        return True
    log.error(
        "issue=#%d could not publish the accepted candidate %s onto PR #%d; "
        "leaving it under adjudication for the retry",
        context.issue.number, context.generation.candidate_sha,
        context.generation.published_pr_number,
    )
    _late_outcome._emit_failure(context, LateFailure.PR_RECONCILE_FAILED)
    _late_parks._park(
        context, _ACCEPTED_PUSH_FAILED_PARK,
        reason=_late_parks.PARK_PR_UNRECONCILED,
    )
    return False


def _proved_before_the_handoff(context: _LateContext, worktree) -> bool:
    """Refuse the handoff where the checkout is not what the verdict accepted.

    The last thing this settlement owns is the worktree, and the two ticks
    that reach here have left it unwatched for different stretches: the one
    that pushes leaves it writable across the push, the pull-request read, and
    the label; the one finishing an interrupted settlement has left it
    writable since a previous process died. Either way what a human accepted
    is one commit with nothing loose beside it, and every stage the label is
    about to hand this issue to works from the CHECKOUT -- the reviewer reads
    a head ahead of the pushed branch as unpublished work, the squash rewrites
    what is on it, the docs pass commits on top.

    So the publication stands and the handoff stops. The branch carries the
    accepted commit either way, the generation stays live and the label stays
    on the adjudication, and a tick taken once the worktree is back on that
    commit finds the pull request already standing on it and finishes from
    there -- no second push, no agent re-run.

    Reached with a checkout in hand on both roads: a push is made from one or
    not at all, and a recorded verdict is refused for a missing worktree well
    before it is settled.
    """
    if _late_accepted._standing_on(
        worktree, context.generation.candidate_sha,
    ):
        return True
    _late_outcome._emit_failure(context, LateFailure.PR_RECONCILE_FAILED)
    _late_parks._park(
        context,
        _UNPROVED_CHECKOUT_PARK.format(
            candidate=context.generation.candidate_sha,
        ),
        reason=_late_parks.PARK_PR_UNRECONCILED,
    )
    return False


def _settled_lease(context: _LateContext) -> str:
    """The head the publication this verdict was taken over is pinned to.

    The retirement below takes the generation -- and the head it froze -- off
    the record, and the push the handoff licenses runs in another stage
    entirely. Without this the publication would read the remote for itself,
    which is right for a candidate nothing has published and wrong for one
    adjudicated against a pull request that already exists: between the proof
    a moment ago and the push, that pull request can move, and an unpinned
    force-push adopts whoever landed as the lease.

    Empty for a pre-publication verdict, whose push has no pull request to be
    pinned to and correctly takes its own reading.
    """
    if not context.generation.has_publication_context:
        return ""
    return context.generation.published_sha


def _released_hold(context: _LateContext) -> bool:
    """Give the held pull request its description back, or park unpublished.

    Run before anything else this reconciliation does, so a release that fails
    leaves the generation exactly as it arrived: live, oversized, and carrying
    the same recorded verdict, which is what makes the retry free.
    """
    release = _late_hold._release_hold(
        context.gh, context.issue, context.generation,
    )
    context.generation = release.generation
    if not release.failed:
        return True
    _late_outcome._emit_failure(context, LateFailure.PLAN_PR_HOLD_FAILED)
    _late_parks._park(
        context, _RELEASE_FAILED_PARK, reason=_late_parks.PARK_HOLD_FAILED,
    )
    return False


def _reconciled_pr(context: _LateContext) -> bool:
    """Point this issue at the pull request the MEASURED commit is on.

    A generation entered on the PUBLISHED side is not searched for at all:
    the record already names the pull request the work is on and the head it
    was standing on when the reading was taken, and neither can be re-derived.
    What that one owes is a proof rather than a lookup, and it is asked one
    owner over.

    The exact-commit half, and the one a search by branch and open state
    cannot do. `pr_number` is whatever the issue recorded when it entered the
    gate -- most often the plan pull request a design discussion opened -- and
    what it names by the time a verdict is settled may be neither the change
    being published nor a change at all: a human can merge or close it, and a
    publication that pushed and died before recording its number leaves the
    accepted commit sitting on a pull request nothing points at.

    Handing either of those on is not cosmetic. `implementing` asks its
    recorded pull request first, and a MERGED one that is no longer the plan
    ends the issue as `done` -- with the adjudicated candidate never
    published; a commit already on a pull request nobody records is published
    a second time, since the ordinary reuse looks for an OPEN one on the
    branch and finds none.

    So the commit is what the pull request is found by, in any state. One that
    carries it is recorded, whatever state it is in, because that is the pull
    request this candidate landed on. Nothing carrying it leaves the recorded
    number alone -- the commit is simply not published yet, and an open plan
    PR is exactly what the ordinary publication reuses -- unless the recorded
    one is settled, which is the pointer that would end the issue.
    """
    if context.generation.has_publication_context:
        return _reconciled_publication(context)
    carrying = context.gh.find_pr_for_commit(
        branch=_worktree_paths._resolve_branch_name(
            context.state, context.spec, context.issue.number,
        ),
        base=context.spec.base_branch,
        head_sha=context.generation.candidate_sha,
    )
    if carrying is _pull_requests.PR_LOOKUP_UNREADABLE:
        return _unreconciled(context, _LOOKUP_FAILED_PARK)
    if carrying is None:
        return _dropped_settled_pr(context)
    log.info(
        "issue=#%d candidate %s is already on PR #%d; recording it rather "
        "than publishing it again",
        context.issue.number, context.generation.candidate_sha,
        carrying.number,
    )
    context.state.set(_PR_NUMBER, carrying.number)
    return True


def _reconciled_publication(context: _LateContext) -> bool:
    """Prove the publication this candidate was measured against is still it.

    The pre-publication road searches for a pull request because it does not
    know of one. This road knows: the entry the gate froze names the pull
    request the work is already on and the head it was standing on, and the
    verdict a human reached is a claim about what THAT pull request would come
    to with the candidate in it. So the two are checked rather than looked up,
    and a check that fails refuses instead of dropping what it could not
    confirm.

    A settled pull request is a refusal here where the pre-publication road
    drops it, and the asymmetry is the point: there, a merged or closed number
    is a stale pointer at a change the candidate is not in, and losing it
    costs nothing because the publication opens the pull request this work
    needs. Here it IS the change -- the branch is on the remote and a human
    settled the pull request carrying it -- so dropping the number would push
    onto that branch and open a second pull request for a change adjudicated
    against the first.

    A head that moved is the same refusal one field over. Something pushed to
    the pull request while the adjudication was open, so what the verdict was
    taken over is not what the branch would come to, and the candidate is
    measured afresh rather than published on a reading that has been overtaken.

    The number is recorded on the way out for the reason the road below
    records one: the publication asks its recorded pull request first, and the
    one this issue entered the gate with may not be the one it was measured
    against.
    """
    generation = context.generation
    number = generation.published_pr_number
    reading = _late_publication._read_publication(
        context.gh, context.issue, number,
    )
    if reading.refused:
        return _unreconciled(context, _RECORDED_PR_UNREADABLE_PARK)
    settled = reading.state
    if settled != _late_publication.OPEN:
        log.error(
            "issue=#%d was adjudicated against PR #%d, which is %s; refusing "
            "to publish the accepted candidate onto a settled publication",
            context.issue.number, number, settled,
        )
        return _unreconciled(
            context,
            _SETTLED_PUBLICATION_PARK.format(number=number, state=settled),
        )
    return _reconciled_head(context, reading.head, number)


def _reconciled_head(
    context: _LateContext, observed: str | None, number: int,
) -> bool:
    """Prove the pull request is standing somewhere this verdict may act on.

    Two heads qualify and everything else is external movement. The frozen one
    is the ordinary answer: nothing has touched the pull request since the
    reading, and the push this verdict earns is still owed.

    The other is the ACCEPTED CANDIDATE where the RECORD says this road put
    it there, and it is this settlement's own push having already landed.
    That push happens before the relabel and the retirement, so a tick that
    died in between comes back to a live generation over a pull request the
    commit is already on -- and read as movement, the one thing that would be
    refused forever is the publication this very verdict made. Recognized,
    the tick carries on from where it stopped: nothing is pushed a second
    time, and the label and the retirement it never reached are what it
    finishes.

    The record is what qualifies it, and asking for one is the whole of the
    safety. On a FRESH pass this call runs before the exemption, the approval,
    and the push behind them, so nothing of this workflow's has touched the
    remote yet: a pull request that moved off the frozen head onto the
    candidate moved because something else -- an agent that pushed its own
    commit is the plain case -- put it there, and taking that for a landed
    settlement would publish and hand on a candidate the adjudication was
    never allowed to release. It refuses with every other moved head instead.
    """
    head = _payloads.as_hex(observed, _formats.COMMIT_LENGTHS)
    if head and head == _this_settlements_own_push(context):
        log.info(
            "issue=#%d finds PR #%d already standing on the accepted "
            "candidate %s; finishing the settlement its push interrupted",
            context.issue.number, number, head,
        )
        context.already_published = True
    elif head != context.generation.published_sha:
        return _moved_publication(context, number, head)
    context.state.set(_PR_NUMBER, number)
    return True


def _this_settlements_own_push(context: _LateContext) -> str:
    """The accepted candidate where a record vouches for its push, or "".

    The two halves of the one window this road opens, and each is durable
    where the candidate on its own is not. The approval is written with the
    exemption in the write immediately ahead of the push and says this
    settlement owes exactly that commit a publication; the receipt is written
    by the push itself, in the same write that drops the approval, and says
    the commit reached the remote. A crash anywhere past that write leaves one
    of the two on the pinned comment, so the retry recognizes the publication
    it made -- and a pass that has written neither has made no push to
    recognize.

    The receipt is read with the head it REPLACED, which is what dates it to
    this settlement. It is never cleared, so on its own it goes on naming a
    commit this issue published rounds ago -- and where the accepted candidate
    IS that commit, a pull request somebody rewound onto it would read as this
    settlement's push having landed. The head this verdict was measured over
    is the one this settlement's push was pinned to, so a receipt recording
    any other head belongs to some earlier publication and answers for
    nothing.
    """
    candidate = context.generation.candidate_sha
    vouched = (
        _gate_parks._approved_commit(context.state),
        _gate_parks._publication_from(
            context.state, context.generation.published_sha,
        ),
    )
    return candidate if candidate and candidate in vouched else ""


def _moved_publication(
    context: _LateContext, number: int, head: str,
) -> bool:
    """Refuse a verdict whose pull request somebody else has moved."""
    frozen = context.generation.published_sha
    log.error(
        "issue=#%d was adjudicated against PR #%d standing at %s and it "
        "stands at %s now; refusing to publish against a publication "
        "that moved",
        context.issue.number, number, frozen, head or "an unreadable head",
    )
    return _unreconciled(
        context,
        _MOVED_PUBLICATION_PARK.format(
            number=number,
            frozen=frozen,
            moved=head or "an unreadable head",
        ),
    )


def _dropped_settled_pr(context: _LateContext) -> bool:
    """Stop recording a pull request this candidate cannot publish onto.

    Reached only when nothing carries the measured commit, so what the issue
    records is about some other change. An OPEN one is left exactly where it
    is: that is the pull request the ordinary publication reuses. A
    merged or closed one is dropped, because carrying it into `implementing`
    is what lets the merged-PR terminal end the issue on a change the
    adjudicated candidate is not in.

    A read that failed is neither answer, and it parks: publishing on the
    strength of it is the one thing this exists to prevent.
    """
    pr_number = _payloads.as_identity(context.state.get(_PR_NUMBER))
    if pr_number is None:
        return True
    try:
        settled = context.gh.pr_state(
            context.gh.get_pr(pr_number),
        ) != _OPEN_PR_STATE
    except Exception:
        log.exception(
            "issue=#%d could not read recorded PR #%d before publishing the "
            "accepted candidate", context.issue.number, pr_number,
        )
        return _unreconciled(context, _RECORDED_PR_UNREADABLE_PARK)
    if settled:
        log.info(
            "issue=#%d recorded PR #%d is settled and does not carry the "
            "accepted candidate; dropping it from the handoff",
            context.issue.number, pr_number,
        )
        context.state.set(_PR_NUMBER, None)
    return True


def _unreconciled(context: _LateContext, message: str) -> bool:
    """Park rather than publish against a pull request nobody could confirm."""
    _late_outcome._emit_failure(context, LateFailure.PR_RECONCILE_FAILED)
    _late_parks._park(
        context, message, reason=_late_parks.PARK_PR_UNRECONCILED,
    )
    return False


def _published(context: _LateContext) -> _LateDisposition | None:
    """Say what was decided, and retire the generation that decided it.

    The two ledgers are the only thing carried across. An obligation the
    remote is owed does not stop being owed because the adjudication that
    recorded it ended well, so the write that drops the rest keeps them -- a
    record with no cycle identity writes exactly what the issue still owes and
    nothing else.

    The notice and the retirement land in one write, so the narrow window
    between them costs at most a repeated comment. The window ahead of them --
    a label already handed on with the generation still live -- costs a tick:
    the relabel guard puts the issue back and this reconciliation runs again,
    finding the hold already released and the exemption already recorded.

    Both of those steps are requests, though, and this is the last place a
    latched close can still be answered: past the retirement the record has no
    cycle identity at all, which is the one state the ending cannot be entered
    from. So the latch is asked between them, and asked again BEHIND the
    retirement -- where the answer is not a refusal but a reinstatement, since
    the generation it would have ended is still in memory.

    The write and that last barrier are held inside `retiring_cycle`, because
    "still in memory" is a claim about THIS thread and the poll runs beside
    it. A poll that reads the record between the two finds no cycle, and
    without the window it would answer "nothing to end", drop the observation,
    and leave the barrier below asking a latch nobody is holding any more.
    Inside it the record's silence proves nothing, the observation is kept,
    and the receipt the poll leaves on the thread is scoped to the cycle this
    window names.

    The window is memory, though, and the barrier behind the write is this
    process's. So the cycle being dropped is recorded in the same write that
    drops it, outside the group that write clears: a process that dies before
    the barrier runs leaves a receipt naming a cycle and a record that still
    says which cycle that was, which is all a later one needs to adopt it.
    """
    _comments._post_issue_comment(
        context.gh, context.issue, context.state,
        _ACCEPTED_NOTICE.format(
            candidate=context.generation.candidate_sha,
            additions=context.generation.additions,
            threshold=context.generation.threshold,
        ),
    )
    live = context.generation
    stopped = _late_owner._latch_stops(context)
    if stopped is not None:
        return stopped
    retiring = _observations.retiring(
        context.spec.slug, context.issue.number, live.cycle_id,
    )
    with retiring.held():
        context.generation = LateGeneration(
            resources=live.resources,
            consumers=live.consumers,
            opaque_resources=live.opaque_resources,
            opaque_consumers=live.opaque_consumers,
        )
        _late_state.record_retired_cycle(context.state, live.cycle_id)
        _late_parks._persist(context)
    return _reinstated(context, live, retiring)


def _reinstated(
    context: _LateContext,
    live: LateGeneration,
    retiring: _observations.RetiringCycle,
) -> _LateDisposition | None:
    """Put back a cycle the retirement write dropped a moment too early.

    That write is a request like every other, so a poll can observe the close
    inside it -- and what it leaves behind is a record with no cycle identity.
    Nothing can end that: the closed-owner sweep reads the cycle to decide
    anything is owed, and a receipt adopted from the thread has no generation
    to be adopted against, so the observation would be stranded for good.

    Asked OF the window rather than of the latch, and that is what makes it
    unmissable: the window decides what it observed as it closes, under the
    lock that closes it, so there is no interval between the answer and the
    exit for a poll to latch a close and post a receipt in. A barrier that
    read the latch itself would leave exactly one.

    The window is also what makes the question answerable at all: without it
    a poll racing the write would have read the retired record, called the
    reading spent, and cleared the very latch this asks about.

    The generation the publication was carrying is still in this call's own
    memory, which is the whole reason the answer here is a reinstatement
    rather than a refusal. It goes back exactly as it was and is cancelled
    from there, so what the ending reads is the cycle that actually ran.

    The published side of the tick is left standing: the exemption is
    recorded, the notice is said, and the label is handed on. None of the
    three is this owner's to take back, and what the ending does with the
    issue where it stands is the cancellation's own business.
    """
    if not retiring.observed:
        return None
    log.warning(
        "repo=%s issue=#%d was observed closed as its accepted candidate was "
        "published; putting cycle %d back on the record so the cancellation "
        "has something to end",
        context.spec.slug, context.issue.number, live.cycle_id,
    )
    context.generation = live
    return _late_owner._latch_stops(context)
