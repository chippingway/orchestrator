# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The bounded pass that spends a classification on a finished issue's artifacts.

The one place in this domain that deletes something nobody asked it to delete.
Everything under it is a reading -- the discovery in ``discovery``, the
classification in ``eligibility``, the fail-closed probes in ``evidence`` and
``claims`` -- and this module is where those readings are turned into three
mutations and one answer per candidate.

What it does NOT touch is as much of its contract as what it does. No workflow
label is written, no pinned state, no comment, and no agent session is started
or stopped: an issue that has ended keeps every record of how it ended, and a
host tidying its own disk must not be able to change what GitHub says happened.
The artifacts are the whole of what this pass owns.

Every gate in front of the mutation fails closed, and they are asked cheapest
first. Whether something is running for this issue right now is asked of an
injected guard, because the answer lives in the process the pass runs beside --
the scheduler holding a claim, a worker mid-tick -- and this layer may not
reach up into the workflow to find it. Then the classification, which is where
the issue's own ending, the pull requests still standing on the branches, and
every reading of the artifacts are established. Then, last and only for a
candidate everything else cleared, whether the checkout has been touched
lately: a tree nobody proved is not one whose modification time says anything.

The mutations are ordered by what git allows and by what a failed pass has to
leave behind. The checkout goes first because a branch checked out somewhere
cannot be deleted. Each branch is then taken on the remote before the clone,
so a remote delete that fails leaves the local ref standing -- and a local ref
is what makes the candidate discoverable again, where a remote-only artifact
would be found only by the next listing of the remote. A pass that stops leaves
everything it had not reached exactly where it was; nothing is written down,
because the discovery that found the candidate once finds what is left of it
again. That is what makes an interrupted pass cost nothing to resume and a
repeated one report the parts already gone as done.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from types import MappingProxyType

from orchestrator.git.worktrees import eligibility, evidence, reclaim
from orchestrator.git.worktrees.models import (
    ArtifactVerdict,
    IssueArtifacts,
    MaintenanceCandidate,
    MaintenanceOutcome,
    MaintenanceReason,
    MaintenanceResult,
    ProbeAnswer,
    ProvenTip,
    Retention,
)
from orchestrator.github.client import GitHubClient

# The channel is named for the worktree-lifecycle domain rather than for this
# module's path: operators filter the rendered `orchestrator.worktree_lifecycle`
# prefix and attach handlers to it, so every artifact this pass takes or
# refuses to take reports where their filters already point.
log = logging.getLogger("orchestrator.worktree_lifecycle")

# Whether anything is currently running for one repository's issue, asked as
# the scheduler's own question is spelled: the repository slug and the issue
# number, and nothing about the artifacts. Injected rather than imported
# because the answer belongs to the process this pass runs beside, and this
# layer may not reach up into the workflow that owns it.
ActivityGuard = Callable[[str, int], bool]

# How long a checkout is left alone after the last thing that touched it. An
# hour is longer than any tick and any agent run's gap between writes, and
# short enough that a host finishing its day's work has its disk back the same
# day. It is a constant rather than a setting because it is a safety margin
# around a deletion, not a knob an operator tunes: what a shorter one buys is
# the chance to delete a tree somebody is standing in.
_QUIET_PERIOD_SECONDS = 3600

# Which outcome each reason is, fixed here so the two fields of a result
# cannot disagree. A retention is the pass declining to act, a failure is a
# step that ran and was refused, and the one reason that cleans is the one
# that reached the end of the teardown.
_OUTCOMES = MappingProxyType({
    MaintenanceReason.RECLAIMED: MaintenanceOutcome.CLEANED,
    MaintenanceReason.UNPROVEN: MaintenanceOutcome.RETAINED,
    MaintenanceReason.RECENT_ACTIVITY: MaintenanceOutcome.RETAINED,
    MaintenanceReason.ACTIVITY_UNREADABLE: MaintenanceOutcome.RETAINED,
    MaintenanceReason.ACTIVE_CLAIM: MaintenanceOutcome.RETAINED,
    MaintenanceReason.CLAIM_UNREADABLE: MaintenanceOutcome.RETAINED,
    MaintenanceReason.TIP_MOVED: MaintenanceOutcome.RETAINED,
    MaintenanceReason.TIP_UNREADABLE: MaintenanceOutcome.RETAINED,
    MaintenanceReason.WORKTREE_REMOVAL_FAILED: MaintenanceOutcome.FAILED,
    MaintenanceReason.REMOTE_DELETE_FAILED: MaintenanceOutcome.FAILED,
    MaintenanceReason.LOCAL_DELETE_FAILED: MaintenanceOutcome.FAILED,
})


def _answered(
    candidate: MaintenanceCandidate,
    reason: MaintenanceReason,
    subject: str = "",
    retentions: tuple[Retention, ...] = (),
) -> MaintenanceResult:
    """One candidate's answer, with the outcome its reason fixes."""
    return MaintenanceResult(
        candidate=candidate,
        outcome=_OUTCOMES[reason],
        reason=reason,
        subject=subject,
        retentions=retentions,
    )


def _claim_reason(
    artifacts: IssueArtifacts, claimed: ActivityGuard,
) -> MaintenanceReason | None:
    """Whether something is running for this issue, or could not be asked.

    First of the gates, because it is the only one that costs nothing and the
    only one whose answer can change under the pass: an issue a worker picks up
    while the classification is being taken is one whose artifacts are about to
    be written in.

    The boundary is total. The guard belongs to the caller, so what it does
    when it fails is not something this module can know -- and an exception out
    of one candidate's guard would otherwise end the pass for every candidate
    behind it.
    """
    try:
        active = claimed(artifacts.spec.slug, artifacts.issue_number)
    except Exception:
        log.warning(
            "issue=#%d could not be asked whether anything is running for it; "
            "leaving its artifacts alone",
            artifacts.issue_number, exc_info=True,
        )
        return MaintenanceReason.CLAIM_UNREADABLE
    return MaintenanceReason.ACTIVE_CLAIM if active else None


def _activity_reason(
    artifacts: IssueArtifacts,
) -> MaintenanceReason | None:
    """Whether this candidate's checkout has been left alone long enough.

    Asked only of a candidate that has a checkout, since a branch has no tree
    to be disturbed and the issue's own ending is what says its work is over.
    Asked last, because a modification time is only worth reading about a tree
    that has already been established as this issue's own.
    """
    worktree = artifacts.worktree
    if worktree is None:
        return None
    quiet = evidence._quiet_checkout(
        worktree, time.time() - _QUIET_PERIOD_SECONDS,
    )
    if quiet is ProbeAnswer.CONFIRMED:
        return None
    if quiet is ProbeAnswer.REFUTED:
        return MaintenanceReason.RECENT_ACTIVITY
    return MaintenanceReason.ACTIVITY_UNREADABLE


def _kept_subject(verdict: ArtifactVerdict) -> str:
    """The artifact the first reason a classification kept this candidate for names."""
    return verdict.retentions[0].subject if verdict.retentions else ""


def _cleared_tips(proven: tuple[ProvenTip, ...]) -> dict[str, str]:
    """The commit each cleared artifact was standing on, by the artifact's name.

    Keyed the way a proof spells its subject -- a branch by name, a checkout by
    path -- so a teardown looking one up names the artifact exactly as the
    classification did rather than deriving a second spelling of it.
    """
    return {tip.subject: tip.sha for tip in proven}


def _checkout_stop(
    worktree: Path, proven: str | None,
) -> MaintenanceReason | None:
    """Whether the checkout is still standing on the commit that was cleared.

    The last reading before the tree comes down, and it is about the commit
    rather than the tree: a linked worktree holds its HEAD and reflog on its
    own, so removing it takes whatever that HEAD names -- and between the proof
    and here, an agent committing moves it to something nobody cleared.

    A candidate with no proof for its checkout is refused rather than removed.
    An eligible verdict always carries one, so reaching this means the two
    halves disagree, and the only safe reading of that is that nothing was
    established.
    """
    tip = evidence._checkout_tip(worktree)
    if proven is None or tip.answer is not ProbeAnswer.CONFIRMED:
        return MaintenanceReason.TIP_UNREADABLE
    if tip.sha != proven:
        return MaintenanceReason.TIP_MOVED
    return None


def _take_checkout(
    candidate: MaintenanceCandidate, cleared: dict[str, str],
) -> MaintenanceResult | None:
    """Take this candidate's checkout down, or say why the pass stops here.

    None is the step being done -- removed, or never there at all -- and a
    result is the pass ending on this artifact. It runs before any branch
    because git refuses to delete a branch a worktree still has checked out,
    so a pass that took the branches first would leave the tree standing and
    the branch beside it undeletable.
    """
    worktree = candidate.artifacts.worktree
    if worktree is None:
        return None
    stopped = _checkout_stop(worktree, cleared.get(str(worktree)))
    if stopped is not None:
        return _answered(candidate, stopped, str(worktree))
    removed = reclaim._remove_recognized_worktree(
        candidate.artifacts.spec, worktree,
    )
    if removed:
        return None
    return _answered(
        candidate, MaintenanceReason.WORKTREE_REMOVAL_FAILED, str(worktree),
    )


def _take_remote_branch(
    candidate: MaintenanceCandidate, branch: str, proven: str,
) -> MaintenanceResult | None:
    """Take one branch off the remote, or say why the pass stops here.

    The remote is asked what it carries before the delete is sent, so the three
    answers stay apart: a branch that is not there is a step already done -- the
    ordinary shape of a merged pull request's head -- a branch at another commit
    is a push nobody here cleared, and a reading that failed is not permission
    to delete anything.

    The delete itself is leased to the same commit, so the answer above is not
    what the deletion rests on: between this read and that push the branch can
    move again, and the remote is what refuses it then.
    """
    spec = candidate.artifacts.spec
    published = evidence._published_tip(spec, branch)
    if published.answer is ProbeAnswer.UNREADABLE:
        return _answered(candidate, MaintenanceReason.TIP_UNREADABLE, branch)
    if published.answer is ProbeAnswer.REFUTED:
        return None
    if published.sha != proven:
        return _answered(candidate, MaintenanceReason.TIP_MOVED, branch)
    if reclaim._delete_remote_branch_at(spec, branch, proven):
        return None
    return _answered(candidate, MaintenanceReason.REMOTE_DELETE_FAILED, branch)


def _take_local_branch(
    candidate: MaintenanceCandidate, branch: str, proven: str,
) -> MaintenanceResult | None:
    """Take one branch out of the clone, or say why the pass stops here.

    Reached only once the remote's copy is gone, which is what keeps a failed
    pass discoverable: the local ref is the cheapest thing the next discovery
    finds, so it is the last artifact of a candidate to go.

    A branch the clone no longer has is a step already done. Anything else is
    put to the pinned delete, which refuses the branch that has moved -- the
    reading here only decides whether there is a deletion to attempt at all.
    """
    spec = candidate.artifacts.spec
    tip = evidence._local_branch_tip(spec, branch)
    if tip.answer is ProbeAnswer.REFUTED:
        return None
    if tip.answer is ProbeAnswer.UNREADABLE:
        return _answered(candidate, MaintenanceReason.TIP_UNREADABLE, branch)
    if tip.sha != proven:
        return _answered(candidate, MaintenanceReason.TIP_MOVED, branch)
    if reclaim._delete_local_ref_at(spec, branch, proven):
        return None
    return _answered(candidate, MaintenanceReason.LOCAL_DELETE_FAILED, branch)


def _take_branches(
    candidate: MaintenanceCandidate, cleared: dict[str, str],
) -> MaintenanceResult | None:
    """Take every cleared branch of this candidate, in the order it was named.

    Each branch goes remote-side first and then locally, rather than every
    remote and then every local, so a candidate carrying both layouts leaves
    one whole branch behind rather than two half-taken ones when a pass stops.

    A branch nothing cleared is passed over. That is a branch the discovery
    named and neither host still has -- gone between the scan and the
    classification -- and a copy nobody proved is one this pass may neither
    delete nor count.

    The first stop ends the candidate. What is left is exactly what the next
    discovery finds, and going on past a refusal would spend deletions on a
    host that has just said it is not in the state anybody read.
    """
    for branch in candidate.artifacts.branches:
        proven = cleared.get(branch)
        if proven is None:
            continue
        stopped = (
            _take_remote_branch(candidate, branch, proven)
            or _take_local_branch(candidate, branch, proven)
        )
        if stopped is not None:
            return stopped
    return None


def _reclaimed(
    candidate: MaintenanceCandidate, proven: tuple[ProvenTip, ...],
) -> MaintenanceResult:
    """Run the whole teardown for one cleared candidate, and say where it got to."""
    cleared = _cleared_tips(proven)
    stopped = (
        _take_checkout(candidate, cleared)
        or _take_branches(candidate, cleared)
    )
    return stopped or _answered(candidate, MaintenanceReason.RECLAIMED)


def _maintained_candidate(
    gh: GitHubClient,
    candidate: MaintenanceCandidate,
    *,
    claimed: ActivityGuard,
) -> MaintenanceResult:
    """Decide about one candidate, and act on it if everything clears it.

    The classification is taken here rather than handed in, because what it
    reads is what the mutations are pinned to: a verdict taken a tick earlier
    would clear commits the artifacts have since left, and the teardown would
    then be spending a proof about branches that no longer exist.
    """
    artifacts = candidate.artifacts
    active = _claim_reason(artifacts, claimed)
    if active is not None:
        return _answered(candidate, active, f"#{artifacts.issue_number}")
    verdict = eligibility._classify_artifacts(gh, artifacts)
    if not verdict.eligible:
        return _answered(
            candidate,
            MaintenanceReason.UNPROVEN,
            _kept_subject(verdict),
            verdict.retentions,
        )
    quiet = _activity_reason(artifacts)
    if quiet is not None:
        return _answered(candidate, quiet, str(artifacts.worktree))
    return _reclaimed(candidate, verdict.proven)


def _maintained_candidates(
    gh: GitHubClient,
    candidates: Iterable[MaintenanceCandidate],
    *,
    claimed: ActivityGuard,
) -> tuple[MaintenanceResult, ...]:
    """Run the pass over every candidate of ONE repository, in its order.

    One client for the lot, so the caller is what splits a discovery spanning
    several repositories: the client is authenticated against one repository,
    and asking it about another's issue number would answer about whatever
    issue happens to carry that number there -- and then delete branches on the
    strength of it.

    Every candidate gets a result, the untouched ones included. A caller
    holding only what was cleaned cannot tell a candidate this pass decided to
    keep from one it never reached, and the second is what a pass that died
    half way through looks like.
    """
    return tuple(
        _maintained_candidate(gh, candidate, claimed=claimed)
        for candidate in candidates
    )
