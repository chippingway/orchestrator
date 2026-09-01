# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which discovered artifacts may be reclaimed, and why the rest are kept.

The classifier over what the scan in ``inventory`` found. It reads and
decides and does nothing else: no label is written, no comment posted, no ref
created, moved, or fetched, on this host or on the remote. A verdict is safe
to take at any point in a tick and safe to throw away, which is what lets the
pass that acts on one be a separate decision from the pass that reaches it.

The order the questions are put in is the order they can settle the answer
in, cheapest claim first. Whether the issue ended at all comes before
anything about the artifacts, because an issue still running keeps its
checkout whatever state the tree is in. An open pull request comes next, and
it is a claim rather than a state: a human reviewing a branch is standing on
it, and the issue underneath having ended does not move them off it. Only
then are the artifacts themselves read, through ``evidence``.

What "eligible" means here is narrow on purpose: every artifact this scan
reported for this issue may be deleted without taking anything with it. The
checkout has to be this issue's own and carrying nothing loose, and every
commit an artifact is holding -- a branch's tip, and the one the checkout's
own HEAD stands on -- has to exist somewhere that outlives it: inside the
configured base, or inside a pull request that has ended. One proof serves
both, so the three shapes a scan can report one issue in reach one verdict
rather than three.

The remote is asked about the branch whatever the base says, because the two
answer different questions: the base says whether the commit survives being
deleted, and the remote says whether the branch this host holds is still the
branch the remote has. A tip already merged can sit under a branch somebody
has since pushed past.

A commit nobody can say where it went is kept, and so is every question that
could not be put: they are all one answer to a caller that only asks whether
it may delete, and that answer has to be no.

What an eligible verdict hands back is the commits it cleared, not only the
permission. The proof is about an object id and the artifact standing on it,
so the teardown that spends the verdict can tell the branch that was cleared
from the branch of that name it finds when it gets there.
"""
from __future__ import annotations

from collections.abc import Iterable
from itertools import chain
from types import MappingProxyType

from orchestrator.git.worktrees import claims, evidence
from orchestrator.git.worktrees.models import (
    ArtifactVerdict,
    BranchTip,
    IssueArtifacts,
    ProbeAnswer,
    ProvenTip,
    Retention,
    RetentionReason,
)
from orchestrator.github.client import GitHubClient

# Nothing is reported from here. Every read this composes is behind a
# boundary in ``claims`` or ``evidence`` that already names what it could not
# take, and a retention is returned rather than logged: what an operator is
# shown about a candidate is the caller's to decide, once, rather than this
# pass's to repeat every tick.

# What each answer about the checkout costs, as the reason it is kept for.
# `CONFIRMED` is absent from both tables on purpose: it is the only answer
# that costs nothing, so a lookup that misses is the checkout passing.
_IDENTITY_REASONS = MappingProxyType({
    ProbeAnswer.UNREADABLE: RetentionReason.CHECKOUT_UNREADABLE,
    ProbeAnswer.REFUTED: RetentionReason.FOREIGN_CHECKOUT,
})

_CLEANLINESS_REASONS = MappingProxyType({
    ProbeAnswer.UNREADABLE: RetentionReason.WORKTREE_UNREADABLE,
    ProbeAnswer.REFUTED: RetentionReason.WORKTREE_DIRTY,
})


def _checkout_retentions(artifacts: IssueArtifacts) -> tuple[Retention, ...]:
    """Why this issue's checkout may not be removed, if it may not.

    Identity first, and the cleanliness read is skipped when it fails.
    Whether a tree is carrying loose files is a question about the tree, and
    a directory that is not this issue's checkout is one whose answer says
    nothing about what removing it would cost -- an empty foreign clone is
    exactly as clean as an empty one of ours, and a probe reporting so would
    be handing over the reason to delete it.

    An issue with no checkout on this host has nothing to keep, which is a
    real answer rather than an unasked question: the scan reports the
    branch-only shape as such, and the reads below would have no path to run
    in.
    """
    worktree = artifacts.worktree
    if worktree is None:
        return ()
    identity = evidence._checkout_identity(
        artifacts.spec, artifacts.issue_number, worktree,
    )
    kept_for = _IDENTITY_REASONS.get(identity)
    if kept_for is None:
        kept_for = _CLEANLINESS_REASONS.get(
            evidence._clean_worktree(worktree),
        )
    if kept_for is None:
        return ()
    return (Retention(kept_for, str(worktree)),)


def _checkout_tip_retentions(
    gh: GitHubClient,
    artifacts: IssueArtifacts,
    base: BranchTip,
    tips: tuple[BranchTip, ...],
    head: BranchTip,
) -> tuple[Retention, ...]:
    """Why the commit this checkout stands on may not be removed with it.

    A checkout is an artifact that HOLDS something rather than a directory
    that merely sits somewhere. A linked worktree keeps a HEAD and a reflog of
    its own, and when no ref points at the commit that HEAD names, those two
    are the only things keeping it reachable -- so removing the checkout is
    what takes the commit, and the proof a branch owes is owed here too.

    A commit one of this issue's reported branches is standing on needs
    nothing further: that branch is proven on its own terms, and whichever way
    its verdict goes the checkout is not the only thing holding the commit.
    Equality is the whole of that test -- a HEAD somewhere further back in a
    branch's history is not something this establishes cheaply, and it fails
    closed.

    A HEAD that names no commit is the shape this exists for, and it is
    reported as a checkout nothing could be established about. `update-ref -d`
    removes a branch a live checkout is on, and afterwards every other reading
    comes back unchanged: the symbolic ref still spells this issue's branch,
    and a tree whose commits went with it still reports clean. That read is
    handed in rather than taken here, because the commit it resolves is also
    what an eligible verdict has to hand over -- one reading, spent twice.

    What is left runs the proof a branch runs, on the branch HEAD is on. The
    commit is a branch tip whichever artifact the report names it through, so
    a rejected issue reported as a checkout alone reaches the same pull
    request -- and the same verdict -- as one reported as a branch. Anything
    narrower would have the three shapes of one issue disagree.
    """
    worktree = artifacts.worktree
    if worktree is None:
        return ()
    on_branch, branch = evidence._head_ref(worktree)
    reads = (head.answer, on_branch)
    if any(read is not ProbeAnswer.CONFIRMED for read in reads):
        return (Retention(
            RetentionReason.CHECKOUT_UNREADABLE, str(worktree),
        ),)
    if any(tip.sha == head.sha for tip in tips):
        return ()
    return _tip_retentions(gh, artifacts, base, branch, head.sha)


def _tip_retentions(
    gh: GitHubClient,
    artifacts: IssueArtifacts,
    base: BranchTip,
    branch: str,
    tip_sha: str,
) -> tuple[Retention, ...]:
    """Why one commit an artifact is holding may not go with it.

    The remote is asked first, and asked whatever the base says, because the
    two answer different questions. The base says whether the commit about to
    be deleted survives the deletion; the remote says whether the branch this
    host holds is still the branch the remote has. A tip the base already
    carries can sit under a remote branch somebody has since pushed past --
    and a reclaim that took the ancestry as the whole answer would report the
    branch as free while work nobody here has seen stands on it.

    An answer that disagrees with the local tip ends it. The two disagreeing
    is divergence nothing here can explain: the branch was force-moved
    locally, or the remote moved on since it was pushed, and either way the
    commits on one side are not the commits on the other.

    A branch the remote does not carry is not divergence and does not end it.
    It is the ordinary shape of a finished issue -- the head branch of a
    merged pull request is deleted there -- so the question passes to the
    base, and from the base to the pull request that carried the commit.
    """
    published = evidence._published_tip(artifacts.spec, branch)
    if published.answer is ProbeAnswer.UNREADABLE:
        return (Retention(RetentionReason.REMOTE_UNREADABLE, branch),)
    if published.answer is ProbeAnswer.CONFIRMED and published.sha != tip_sha:
        return (Retention(RetentionReason.REMOTE_DIVERGENCE, branch),)
    contained = evidence._base_contains(artifacts.spec, base, tip_sha)
    if contained is ProbeAnswer.CONFIRMED:
        return ()
    if contained is ProbeAnswer.UNREADABLE:
        return (Retention(RetentionReason.BASE_UNREADABLE, branch),)
    return claims._commit_accounting(gh, branch, tip_sha)


def _branch_retentions(
    gh: GitHubClient,
    artifacts: IssueArtifacts,
    base: BranchTip,
    branch: str,
    tip: BranchTip,
) -> tuple[Retention, ...]:
    """Why one of this issue's branches may not be deleted, if it may not.

    The proof runs on the tip rather than on a count of commits, because the
    tip is the only thing the two ways out are stated in: the base either
    contains that commit or it does not, and a pull request either carries it
    or carries something else. A branch whose tip the base already holds is
    the ordinary merged shape and needs nothing further.

    `base` and `tip` are both established once for the whole candidate and
    handed in: the base because every artifact under this issue is measured
    against the same commit, and the tip because the checkout beside this
    branch has to know what it is standing on to tell whether the branch is
    already holding it.

    A branch that has gone since the scan named it is eligible rather than a
    problem. There is nothing left to delete, and the alternative -- keeping
    an issue back over an artifact that no longer exists -- is a retention no
    operator could ever settle.
    """
    if tip.answer is ProbeAnswer.UNREADABLE:
        return (Retention(RetentionReason.BRANCH_UNREADABLE, branch),)
    if tip.answer is ProbeAnswer.REFUTED:
        return ()
    return _tip_retentions(gh, artifacts, base, branch, tip.sha)


def _checkout_head(
    artifacts: IssueArtifacts, kept: tuple[Retention, ...],
) -> BranchTip:
    """The commit this issue's checkout stands on, when it is worth resolving.

    Answered as the read that established nothing in the two cases where it is
    not taken at all: an issue with no checkout on this host, and a checkout
    something about the tree itself already refuses. The second is the reason
    the read is skipped rather than merely ignored -- a directory that is not
    this issue's checkout is one whose HEAD says nothing about what removing
    it would cost.
    """
    if artifacts.worktree is None or kept:
        return BranchTip(answer=ProbeAnswer.UNREADABLE)
    return evidence._checkout_tip(artifacts.worktree)


def _proven_tips(
    artifacts: IssueArtifacts, head: BranchTip, tips: tuple[BranchTip, ...],
) -> tuple[ProvenTip, ...]:
    """Every commit this reading found an artifact of this issue standing on.

    The proof an eligible verdict is spent on, in the artifacts' own order:
    the checkout first, since that is the order the teardown takes them down
    in, and then one entry per branch the clone still carries.

    A branch that has gone since the scan named it contributes nothing, which
    is the same answer the classification gives it: there is no commit to
    clear because there is no longer a branch holding one. A teardown that
    found the name back in place would then be holding no proof for it, and
    proof is what it deletes on.
    """
    proven = tuple(
        ProvenTip(branch, tip.sha)
        for branch, tip in zip(artifacts.branches, tips)
        if tip.answer is ProbeAnswer.CONFIRMED
    )
    if artifacts.worktree is None or head.answer is not ProbeAnswer.CONFIRMED:
        return proven
    return (ProvenTip(str(artifacts.worktree), head.sha), *proven)


def _artifact_reading(
    gh: GitHubClient, artifacts: IssueArtifacts,
) -> tuple[tuple[Retention, ...], tuple[ProvenTip, ...]]:
    """What the artifacts say: why they are kept, and what they are holding.

    Both sides are read even when the first one already refuses, because what
    an operator is being handed is a list of what to go and look at. A dirty
    checkout beside a branch nothing accounts for is two pieces of work in
    two places, and reporting only the first sends them back for the second
    on the tick after they clear it.

    Both sides also owe the same proof, which is why the checkout is not done
    once it is clean: a commit is held by whatever points at it, and for a
    checkout whose branch is gone that is the checkout. Its tip is put to the
    proof only when nothing about the checkout itself already refuses -- a
    tree that could not be read establishes nothing about what it holds either
    -- and the branch tips are resolved first, so a commit one of them is
    already standing on is one the removal cannot strand.

    What the base is on is asked of the remote once and handed to every
    proof, since every artifact under this issue is measured against the same
    commit -- and it is asked only when there is an artifact to measure.

    The tips come back beside the reasons because they are the same readings.
    A caller that took the verdict and then re-read them would be acting on
    commits nobody adjudicated: between the two readings an agent can commit,
    and the branch that comes back is the one the proof is not about.
    """
    checkout = _checkout_retentions(artifacts)
    if artifacts.worktree is None and not artifacts.branches:
        return checkout, ()
    base = evidence._published_tip(
        artifacts.spec, artifacts.spec.base_branch,
    )
    tips = tuple(
        evidence._local_branch_tip(artifacts.spec, branch)
        for branch in artifacts.branches
    )
    head = _checkout_head(artifacts, checkout)
    if not checkout:
        checkout = _checkout_tip_retentions(gh, artifacts, base, tips, head)
    return (
        checkout + _branch_reasons(gh, artifacts, base, tips),
        _proven_tips(artifacts, head, tips),
    )


def _branch_reasons(
    gh: GitHubClient,
    artifacts: IssueArtifacts,
    base: BranchTip,
    tips: tuple[BranchTip, ...],
) -> tuple[Retention, ...]:
    """Every reason this issue's branches give, in the order they were named.

    Each branch is put to the proof against the tip already read for it, so
    the reading the proof is about and the reading the caller hands on as what
    it cleared are one and the same.
    """
    return tuple(chain.from_iterable(
        _branch_retentions(gh, artifacts, base, branch, tip)
        for branch, tip in zip(artifacts.branches, tips)
    ))


def _classify_artifacts(
    gh: GitHubClient, artifacts: IssueArtifacts,
) -> ArtifactVerdict:
    """Whether one discovered candidate's artifacts may be reclaimed.

    The remote gates come first and each one settles the verdict on its own.
    An issue that could not be fetched, one that has not ended, and one whose
    pinned state could not be read are all answers about whether this
    candidate is a candidate at all, and reading the host's artifacts under
    any of them would spend git processes on a question already closed.

    The pinned state is read after the ending is established rather than
    beside the issue, for the same reason: it costs a comment listing on
    every closed issue this host holds artifacts for, and an issue still
    running never needs it.

    The issue number every gate is spelled against is the candidate's own,
    never one read back off the fetched issue: the artifacts are what this
    verdict is about, and the attribute naming them on the issue is one more
    lazy read that can fail.

    Only the verdict that clears the artifacts carries what it cleared. A
    retained one has established that these commits stay, and a proof beside
    that answer would be a permission nothing here gave.
    """
    issue = claims._fetched_issue(gh, artifacts.issue_number)
    if issue is None:
        return ArtifactVerdict(artifacts, (Retention(
            RetentionReason.ISSUE_UNREADABLE, f"#{artifacts.issue_number}",
        ),))
    ended = claims._terminal_retentions(issue, artifacts.issue_number)
    if ended:
        return ArtifactVerdict(artifacts, ended)
    state = claims._read_state(gh, issue, artifacts.issue_number)
    if isinstance(state, Retention):
        return ArtifactVerdict(artifacts, (state,))
    claimed = claims._open_pull_request_retentions(
        gh, artifacts.spec, artifacts.issue_number, artifacts.branches, state,
    )
    if claimed:
        return ArtifactVerdict(artifacts, claimed)
    return _artifact_verdict(gh, artifacts)


def _artifact_verdict(
    gh: GitHubClient, artifacts: IssueArtifacts,
) -> ArtifactVerdict:
    """The verdict the artifacts' own reading comes to, once GitHub is done.

    The two halves of that reading are exclusive by construction: a candidate
    is cleared for exactly the commits it was found holding, and one that is
    kept hands over nothing at all.
    """
    kept, proven = _artifact_reading(gh, artifacts)
    if kept:
        return ArtifactVerdict(artifacts, kept)
    return ArtifactVerdict(artifacts, proven=proven)


def _classified_candidates(
    gh: GitHubClient, candidates: Iterable[IssueArtifacts],
) -> tuple[ArtifactVerdict, ...]:
    """Classify every candidate one repository's scan reported, in its order.

    One client for the lot, so the caller is the one that splits an inventory
    spanning several repositories: the client is authenticated against one
    repository and asking it about another repository's issue number would
    answer about whatever issue happens to carry that number there.

    Every candidate gets a verdict, the retained ones included. A caller
    holding only the eligible ones cannot tell an issue it may not touch from
    one this pass never reached, and the second is what a failure looks like.
    """
    return tuple(
        _classify_artifacts(gh, artifacts) for artifacts in candidates
    )
