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
snapshot they are cut from, and superseding the plan pull request are one
transaction and belong together; what this owner owes it is the guarantee it
cannot check for itself -- that the outcome it is given was re-checked against
an owner read taken after the agent finished.

A `single` is reconciled here, and the whole of it is an EXEMPTION rather than
a publication. The candidate is already committed in the developer's own
worktree and the ordinary implementing publication is what pushes it, reuses
or opens its pull request, and hands it to review; what the size gate needs is
a durable record that this exact commit has been adjudicated, or it would
measure the same candidate past the same ceiling and adjudicate it again
forever. So the exemption names the measured commit and only it -- work
committed after the verdict is work nobody adjudicated, and the gate measures
it as the fresh candidate it is.

Two things it deliberately does not do. It creates no snapshot: a snapshot
exists so children can be cut from a candidate that is about to be superseded,
and an accepted candidate is superseded by nothing -- it publishes as itself,
from the branch it is already on. And it restores rather than rewrites: the
held plan PR gets back the description this generation replaced, and what
happens to that pull request afterwards is the ordinary reconciliation's --
the publication that follows reuses it and rewrites its body when the push
lands on it, and leaves it alone when it does not.

The order is chosen so every window a crash can land in is one the next tick
repairs. The hold is released first, while nothing else has moved. The
exemption is written next and the generation is still live behind it, so the
issue is still an adjudication in flight. Only then is the label handed on,
and only after that is the generation cleared -- because a `decomposing` issue
with no generation on it is one the INITIAL decomposer would pick up and
re-decompose, and a `implementing` issue with a live generation is one the
relabel guard puts back and this tick re-settles.
"""
from __future__ import annotations

import logging
from dataclasses import replace

from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.github import pull_requests as _pull_requests
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.late_split import exemption as _exemption
from orchestrator.workflow.late_split import payloads as _payloads
from orchestrator.workflow.late_split.models import (
    LateFailure,
    LateGeneration,
    LateVerdict,
)
from orchestrator.workflow.stages.decomposition import late_hold as _late_hold
from orchestrator.workflow.stages.decomposition import (
    late_outcome as _late_outcome,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    _GuardedSplit,
    _LateAdjudicationRun,
    _LateContext,
    _LateDisposition,
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
    "but the hold on its plan PR could not be taken off -- so nothing was "
    "handed on for publication and the pull request still reads as held. "
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
    state cannot make: the hold comes off the plan pull request, and the pull
    request this issue RECORDS is settled against the measured commit, so what
    the handoff names is a change the accepted candidate is actually in.
    Everything durable goes out in one write ahead of the label that hands it
    on, since the label is what makes another stage read it.

    Never a snapshot. A snapshot is what children are cut from when the
    candidate they came out of is about to be superseded, and an accepted
    candidate supersedes nothing: it publishes as itself, from the branch it
    is already committed on, so preserving a copy of it would create an
    obligation with nothing on the other end.
    """
    if not _released_hold(context) or not _reconciled_pr(context):
        return _late_outcome._finished(context, _LateDisposition.PARKED)
    _exemption.record_exemption(
        context.state, context.generation.candidate_sha,
    )
    _late_outcome._persist(context)
    context.gh.set_workflow_label(context.issue, WorkflowLabel.IMPLEMENTING)
    _published(context)
    return replace(
        finished,
        disposition=_LateDisposition.SETTLED,
        generation=context.generation,
    )


def _released_hold(context: _LateContext) -> bool:
    """Give the held plan PR its description back, or park without publishing.

    Run before anything else this reconciliation does, so a release that fails
    leaves the generation exactly as it arrived: live, oversized, and carrying
    the same recorded verdict, which is what makes the retry free.
    """
    release = _late_hold._release_plan_pr_hold(
        context.gh, context.issue, context.generation,
    )
    context.generation = release.generation
    if not release.failed:
        return True
    _late_outcome._emit_failure(context, LateFailure.PLAN_PR_HOLD_FAILED)
    _late_outcome._park(
        context, _RELEASE_FAILED_PARK, reason=_late_outcome.PARK_HOLD_FAILED,
    )
    return False


def _reconciled_pr(context: _LateContext) -> bool:
    """Point this issue at the pull request the MEASURED commit is on.

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


def _dropped_settled_pr(context: _LateContext) -> bool:
    """Stop recording a pull request this candidate cannot publish onto.

    Reached only when nothing carries the measured commit, so what the issue
    records is about some other change. An OPEN one is left exactly where it
    is: that is the plan pull request the ordinary publication reuses. A
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
    _late_outcome._park(
        context, message, reason=_late_outcome.PARK_PR_UNRECONCILED,
    )
    return False


def _published(context: _LateContext) -> None:
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
    """
    _comments._post_issue_comment(
        context.gh, context.issue, context.state,
        _ACCEPTED_NOTICE.format(
            candidate=context.generation.candidate_sha,
            additions=context.generation.additions,
            threshold=context.generation.threshold,
        ),
    )
    context.generation = LateGeneration(
        resources=context.generation.resources,
        consumers=context.generation.consumers,
        opaque_resources=context.generation.opaque_resources,
        opaque_consumers=context.generation.opaque_consumers,
    )
    _late_outcome._persist(context)
