# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The hold and the pull request a candidate owes before it is handed on.

Two reconciliations, run in that order, and the second is the one a search by
branch and open state cannot make. The hold comes off the pull request this
generation marked, and the pull request the issue RECORDS is settled against
the measured commit, so what the handoff names is a change that commit is
actually in.

Both roads out of the gate reach this owner: the verdict a `single` earned, and
the handoff of a candidate a remeasurement put back under the ceiling without
any adjudication at all. Neither may hand the issue on with a "do not merge"
notice nobody will reclaim, or with `pr_number` naming a change the candidate
is not in -- the retirement a moment later reads a record about SIZE and knows
nothing about either.

The hold is RESTORED rather than rewritten: the held pull request gets back the
description this generation replaced, and what happens to it afterwards is the
ordinary publication's -- that one reuses it and rewrites its body when the
push lands on it, and leaves it alone when it does not.

Which reconciliation the pull request gets splits on the side of publication
the candidate was measured on. A candidate nothing had published is SEARCHED
for by commit, because nothing on the record names where it went. One measured
against a pull request the remote already carries is PROVED instead: the entry
the gate froze names that pull request and the head it was standing on, neither
can be re-derived, and a check that fails refuses rather than dropping what it
could not confirm.
"""
from __future__ import annotations

import logging

from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.github import pull_requests as _pull_requests
from orchestrator.workflow.late_split import payloads as _payloads
from orchestrator.workflow.late_split.models import LateFailure
from orchestrator.workflow.stages.decomposition import (
    late_hold as _late_hold,
    late_outcome as _late_outcome,
    late_parks as _late_parks,
    late_proof as _late_proof,
    late_publication as _late_publication,
)
from orchestrator.workflow.stages.decomposition.late_models import _LateContext

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
    function over.

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
        return _late_proof._unreconciled(context, _LOOKUP_FAILED_PARK)
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

    A head that moved is the same refusal one field over, and the owner that
    tells it apart from this settlement's own landed push is asked for it.

    The number is recorded on the way out for the reason the road above
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
        return _late_proof._unreconciled(context, _RECORDED_PR_UNREADABLE_PARK)
    settled = reading.state
    if settled != _late_publication.OPEN:
        log.error(
            "issue=#%d was adjudicated against PR #%d, which is %s; refusing "
            "to publish the accepted candidate onto a settled publication",
            context.issue.number, number, settled,
        )
        return _late_proof._unreconciled(
            context,
            _SETTLED_PUBLICATION_PARK.format(number=number, state=settled),
        )
    if not _late_proof._reconciled_head(context, reading.head, number):
        return False
    context.state.set(_PR_NUMBER, number)
    return True


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
        return _late_proof._unreconciled(
            context, _RECORDED_PR_UNREADABLE_PARK,
        )
    if settled:
        log.info(
            "issue=#%d recorded PR #%d is settled and does not carry the "
            "accepted candidate; dropping it from the handoff",
            context.issue.number, pr_number,
        )
        context.state.set(_PR_NUMBER, None)
    return True
