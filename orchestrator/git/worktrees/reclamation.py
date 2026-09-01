# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Taking down the artifacts one eligible verdict cleared.

The destructive half of the artifact domain, and the only owner in it that
writes anything: ``eligibility`` decides, and this spends what it decided. A
verdict is the whole of the permission -- nothing here re-derives it, and one
that keeps its candidate is refused before a single read is taken.

What the verdict established is established again at the boundary it is about
to be spent at, because a proof is a statement about a moment. Between the
classification and the teardown an agent can write in the tree, a human can
commit onto the branch, and somebody can push past what the remote carried. So
the checkout is proved to be this issue's own, carrying nothing loose, and
standing on the commit that was cleared before it is removed; the local branch
is deleted through a ref update naming the old value, which makes the check
and the deletion one step; and the remote branch goes under a lease pinned to
the same commit.

Nothing is forced. The removal runs without `--force` and both deletions state
what they expect, so the worst this can do to work nobody adjudicated is fail
to delete something.

**Absent is success.** A checkout already gone and a branch already deleted
are the ordinary shape of a second pass, and reporting them as failures would
keep an issue in a report forever over artifacts nobody can find.

**Order is what keeps a failure findable.** The checkout comes down before the
branch it is on, which is git's rule as much as this module's. The remote
branch comes down before the local one, which is this module's own: what the
scan in ``inventory`` reads a candidate back off is the checkout and the local
branch, so a local artifact deleted while a remote one survives takes with it
the last thing that would have led anybody back to the remote. Every step
therefore refuses while a surface behind it is still standing, and a teardown
that failed halfway leaves this host holding the thread.

That is the whole of the retry, too: nothing is remembered here. A surface
that failed is an artifact still on disk or still on the remote, so the next
scan reports the issue again, the classification proves it again, and this
runs again -- across a restart exactly as within one process.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from itertools import chain
from pathlib import Path
from types import MappingProxyType

from orchestrator.git import authentication, commands, locks
from orchestrator.git.worktrees import evidence, paths
from orchestrator.git.worktrees.models import (
    ArtifactReclamation,
    ArtifactSurface,
    ArtifactVerdict,
    BranchTip,
    IssueArtifacts,
    ProbeAnswer,
    SurfaceOutcome,
    SurfaceResult,
)

# The channel is named for the worktree-lifecycle domain rather than for this
# module's path: operators filter the rendered `orchestrator.worktree_lifecycle`
# prefix and attach handlers to it, so every artifact this reclaims -- and
# every one it will not -- reports where their filters already point.
log = logging.getLogger("orchestrator.worktree_lifecycle")

# What a branch is called when it is named to git in full. Both deletions name
# the ref rather than the branch, so a branch spelled like an option cannot be
# read as one and a tag sharing a branch's name cannot be resolved instead.
_BRANCH_REF_PREFIX = "refs/heads/"

# What the clone is asked about a branch nobody could resolve, and what the
# remote is, in the log line that names which of them would not answer.
_CLONE = "the clone"

_REMOTE = "the remote"


def _branch_ref(branch: str) -> str:
    """The fully-qualified ref one of this issue's branch names spells."""
    return f"{_BRANCH_REF_PREFIX}{branch}"


def _reclaim_artifacts(verdict: ArtifactVerdict) -> ArtifactReclamation:
    """Take down every artifact one verdict cleared, one surface at a time.

    The verdict is the permission and the proof both, and it is taken as
    handed over: a candidate this pass may not touch is one whose reads have
    already been paid for, and putting them again here would be a second
    opinion nobody asked for -- one that can disagree with the first.

    The checkout is settled before any branch is reached, because the answer
    it gives decides whether a branch may be reached at all: git deletes a
    branch a live checkout is standing on without complaint, and the reference
    that checkout keeps is the one thing that would still lead back to it.
    """
    artifacts = verdict.artifacts
    if not verdict.eligible:
        log.warning(
            "issue=#%d refusing to reclaim: this verdict keeps the candidate",
            artifacts.issue_number,
        )
        return ArtifactReclamation(artifacts, _untouched(artifacts))
    proven = MappingProxyType({tip.subject: tip.sha for tip in verdict.proven})
    checkout = _reclaimed_checkout(artifacts, proven)
    freed = all(
        taken.outcome is not SurfaceOutcome.FAILED for taken in checkout
    )
    return _reported(artifacts, checkout + tuple(chain.from_iterable(
        _reclaimed_branch(artifacts, branch, proven, freed=freed)
        for branch in artifacts.branches
    )))


def _reported(
    artifacts: IssueArtifacts, surfaces: tuple[SurfaceResult, ...],
) -> ArtifactReclamation:
    """The teardown's answer, with what it destroyed said out loud once.

    Said here rather than at each step, and said at all rather than left to
    the caller: a deletion is the one thing in this domain that cannot be
    reconstructed afterwards, so an operator asking later what became of a
    branch finds the answer in the log whether or not whoever asked for the
    teardown kept the record it returned.
    """
    cleaned = tuple(
        f"{taken.surface} {taken.subject}"
        for taken in surfaces
        if taken.outcome is SurfaceOutcome.CLEANED
    )
    if cleaned:
        log.info(
            "issue=#%d reclaimed %s",
            artifacts.issue_number, ", ".join(cleaned),
        )
    return ArtifactReclamation(artifacts, surfaces)


def _untouched(artifacts: IssueArtifacts) -> tuple[SurfaceResult, ...]:
    """Every surface this candidate has, as one nothing was done to.

    What a verdict that does not clear its candidate is answered with. The
    surfaces are named rather than the answer left empty, because an empty
    report is what a candidate with nothing left to reclaim gets -- and this
    one has everything left.
    """
    checkout = () if artifacts.worktree is None else (SurfaceResult(
        ArtifactSurface.WORKTREE,
        str(artifacts.worktree),
        SurfaceOutcome.FAILED,
    ),)
    return checkout + tuple(chain.from_iterable(
        _branch_surfaces(branch, SurfaceOutcome.FAILED, SurfaceOutcome.FAILED)
        for branch in artifacts.branches
    ))


def _branch_surfaces(
    branch: str, remote: SurfaceOutcome, local: SurfaceOutcome,
) -> tuple[SurfaceResult, ...]:
    """One branch's two surfaces, in the order they are taken down in."""
    return (
        SurfaceResult(ArtifactSurface.REMOTE_BRANCH, branch, remote),
        SurfaceResult(ArtifactSurface.LOCAL_BRANCH, branch, local),
    )


def _reclaimed_checkout(
    artifacts: IssueArtifacts, proven: Mapping[str, str],
) -> tuple[SurfaceResult, ...]:
    """Remove this issue's checkout, or say why it is still there.

    Nothing at all when the scan reported no checkout: a surface an issue does
    not have is not one a teardown left standing, and reporting it as one
    would leave a branch-only candidate unable to ever come back settled.
    """
    worktree = artifacts.worktree
    if worktree is None:
        return ()
    return (SurfaceResult(
        ArtifactSurface.WORKTREE,
        str(worktree),
        _removed_checkout(artifacts, worktree, proven.get(str(worktree))),
    ),)


def _removed_checkout(
    artifacts: IssueArtifacts, worktree: Path, proven_sha: str | None,
) -> SurfaceOutcome:
    """The checkout removal, inside the boundary that owns its failures.

    Lock-held from the revalidation through the removal, because the two are
    one decision: `worktree remove` writes the parent clone's administrative
    files, which is the store every other worktree mutation serializes on, so
    a reading taken outside the lock could be answering about a tree another
    thread is in the middle of creating.

    Total, like every probe under it. One candidate's unlucky tick may not end
    the pass the rest of them are in, and a caller holding a partial teardown
    it cannot describe is worse off than one holding a surface that failed.
    """
    try:
        with locks._target_root_lock(artifacts.spec.target_root):
            return _removal_under_lock(artifacts, worktree, proven_sha)
    except Exception:
        log.exception(
            "issue=#%d removing the checkout %s raised",
            artifacts.issue_number, worktree,
        )
        return SurfaceOutcome.FAILED


def _removal_under_lock(
    artifacts: IssueArtifacts, worktree: Path, proven_sha: str | None,
) -> SurfaceOutcome:
    """Present, still what was cleared, and then gone.

    `worktree remove` without `--force`, which is git's own last word on the
    same question the revalidation just asked: a tree carrying modified or
    untracked files is refused rather than deleted. The probe above it is not
    made redundant by that -- it tells a tree that PROVED it is carrying
    nothing from one nobody could read -- but between a reading and a deletion
    there is no such thing as too many ways to say no.
    """
    present = _checkout_present(worktree)
    if present is ProbeAnswer.REFUTED:
        return SurfaceOutcome.ABSENT
    if present is ProbeAnswer.UNREADABLE or not _still_cleared(
        artifacts, worktree, proven_sha,
    ):
        return SurfaceOutcome.FAILED
    removed = commands._git_hardened(
        "worktree", "remove", str(worktree), cwd=artifacts.spec.target_root,
    )
    if removed.returncode == 0:
        return SurfaceOutcome.CLEANED
    log.warning(
        "issue=#%d worktree remove of %s failed: %s",
        artifacts.issue_number, worktree, (removed.stderr or "").strip(),
    )
    return SurfaceOutcome.FAILED


def _checkout_present(worktree: Path) -> ProbeAnswer:
    """Whether there is anything at this path to remove.

    `REFUTED` is the path being gone, which is a removal that already
    happened. `UNREADABLE` is the host refusing to say -- a directory this
    process may not stat, a symlink loop -- and it is kept apart from the
    first because of what the first releases: git deletes a branch a live
    checkout is standing on, so "nothing here" spent on a checkout nobody
    could see is how a live tree loses the ref under it.

    Read through `lstat` rather than `Path.exists`, which answers False for
    every `OSError` it meets and would hand exactly that reading over as an
    absence.
    """
    try:
        worktree.lstat()
    except FileNotFoundError:
        return ProbeAnswer.REFUTED
    except OSError as read_error:
        log.warning(
            "the checkout %s could not be read: %s", worktree, read_error,
        )
        return ProbeAnswer.UNREADABLE
    return ProbeAnswer.CONFIRMED


def _still_cleared(
    artifacts: IssueArtifacts, worktree: Path, proven_sha: str | None,
) -> bool:
    """Whether this checkout is still the one the verdict cleared.

    The path first, and against the one the creators derive rather than
    against anything on disk: a verdict is a value a caller hands over, and
    the boundary does not take its word for which directory it may delete.

    Then the readings the classification took, taken again. The tree is a
    worktree of the configured clone and on a branch this issue publishes
    under, its HEAD is on the commit that was cleared, and it is carrying
    nothing loose.

    The tip is compared rather than merely resolved, which is what makes work
    made after the proof survive: the commit somebody cleared is somewhere the
    deletion cannot reach it, and the one a HEAD has moved onto since may be
    held by this checkout's own reflog alone. A HEAD that would not resolve at
    all fails the same comparison, because what it answers with is not a
    commit.
    """
    if worktree != paths._worktree_path(
        artifacts.spec, artifacts.issue_number,
    ):
        log.warning(
            "issue=#%d refusing to remove %s: not where this issue's checkout "
            "belongs", artifacts.issue_number, worktree,
        )
        return False
    identity = evidence._checkout_identity(
        artifacts.spec, artifacts.issue_number, worktree,
    )
    if identity is not ProbeAnswer.CONFIRMED:
        log.warning(
            "issue=#%d keeping %s: it is no longer this issue's own checkout "
            "(%s)", artifacts.issue_number, worktree, identity,
        )
        return False
    if evidence._checkout_tip(worktree).sha != proven_sha:
        log.warning(
            "issue=#%d keeping %s: its HEAD is no longer the %r this verdict "
            "cleared", artifacts.issue_number, worktree, proven_sha,
        )
        return False
    if evidence._clean_worktree(worktree) is not ProbeAnswer.CONFIRMED:
        log.warning(
            "issue=#%d keeping %s: it has not proved it is carrying nothing "
            "loose", artifacts.issue_number, worktree,
        )
        return False
    return True


def _reclaimed_branch(
    artifacts: IssueArtifacts,
    branch: str,
    proven: Mapping[str, str],
    *,
    freed: bool,
) -> tuple[SurfaceResult, ...]:
    """Take one of this issue's branches down on both hosts, remote first.

    Ownership before anything else, and re-derived rather than trusted: the
    two names this issue publishes under are the only refs a teardown for it
    may delete, here or on the remote. Anything else is a candidate two
    repositories sharing a clone disagreed about, or a caller that assembled
    the artifacts itself -- and either way the branch it names is somebody's.

    The local tip is read once and spent on both steps, because it settles the
    same question for each: whether the branch this host holds is still the
    one the verdict cleared. A branch that has moved releases neither, so a
    commit made after the proof keeps the remote copy of that branch as surely
    as it keeps the local one.
    """
    if branch not in paths._issue_branch_names(
        artifacts.spec, artifacts.issue_number,
    ):
        log.warning(
            "issue=#%d refusing to reclaim %r: not a branch this issue "
            "publishes under", artifacts.issue_number, branch,
        )
        return _branch_surfaces(
            branch, SurfaceOutcome.FAILED, SurfaceOutcome.FAILED,
        )
    cleared_sha = proven.get(branch)
    tip = evidence._local_branch_tip(artifacts.spec, branch)
    remote = SurfaceOutcome.FAILED
    if _unmoved(artifacts, branch, tip, cleared_sha):
        remote = _reclaimed_remote_branch(artifacts, branch, cleared_sha)
    return _branch_surfaces(branch, remote, _reclaimed_local_branch(
        artifacts, branch, tip,
        released=freed and remote is not SurfaceOutcome.FAILED,
    ))


def _unmoved(
    artifacts: IssueArtifacts,
    branch: str,
    tip: BranchTip,
    proven_sha: str | None,
) -> bool:
    """Whether this branch is still what the verdict cleared, or already gone.

    Gone counts, which is why this is not a plain comparison. A branch deleted
    since the classification leaves nothing on this host to protect, while the
    copy of it the remote carries is still the commit somebody proved -- so
    the remote step goes on rather than being stranded by a local absence
    nobody can act on.

    Everything else is a no. A tip that could not be read establishes nothing,
    and a tip that is not the proven one is work made after the proof; neither
    releases the branch on either host.
    """
    if tip.answer is ProbeAnswer.REFUTED:
        return True
    if tip.answer is ProbeAnswer.CONFIRMED and tip.sha == proven_sha:
        return True
    log.warning(
        "issue=#%d keeping %r: the clone holds %r where the verdict cleared "
        "%r", artifacts.issue_number, branch, tip.sha, proven_sha,
    )
    return False


def _reclaimed_remote_branch(
    artifacts: IssueArtifacts, branch: str, proven_sha: str | None,
) -> SurfaceOutcome:
    """Delete the remote's copy of one branch, or say why it is still there.

    Asked of the remote itself rather than of `refs/remotes/<remote>/<branch>`
    for the reason the classification asks that way: the mirror is a local ref
    in the store every per-issue worktree shares, and this step's next move is
    a deletion on somebody's repository.

    A branch the remote does not carry is the ordinary terminal shape -- a
    merged pull request's head branch is deleted there -- and it is success.
    """
    published = evidence._published_tip(artifacts.spec, branch)
    if published.answer is not ProbeAnswer.CONFIRMED:
        return _unresolved(artifacts, branch, published, _REMOTE)
    if published.sha != proven_sha:
        log.warning(
            "issue=#%d keeping %r on the remote: it carries %r where the "
            "verdict cleared %r",
            artifacts.issue_number, branch, published.sha, proven_sha,
        )
        return SurfaceOutcome.FAILED
    return _deleted_remote_branch(artifacts, branch, published.sha)


def _deleted_remote_branch(
    artifacts: IssueArtifacts, branch: str, expected: str,
) -> SurfaceOutcome:
    """The push that deletes, inside the boundary that owns its failures.

    Pinned to the commit just read, which is the commit the verdict cleared:
    the same lease the immutable snapshot namespace is reclaimed under. A
    branch somebody pushed to between the reading and this push fails the
    lease instead of being overwritten by it, which is the only revalidation
    available on a host this process does not hold a lock on.
    """
    try:
        deleted = authentication._delete_remote_ref(
            artifacts.spec,
            artifacts.spec.target_root,
            ref=_branch_ref(branch),
            expected=expected,
        )
    except Exception:
        log.exception(
            "issue=#%d deleting the remote branch %r raised",
            artifacts.issue_number, branch,
        )
        return SurfaceOutcome.FAILED
    return SurfaceOutcome.CLEANED if deleted else SurfaceOutcome.FAILED


def _reclaimed_local_branch(
    artifacts: IssueArtifacts,
    branch: str,
    tip: BranchTip,
    *,
    released: bool,
) -> SurfaceOutcome:
    """Delete one local branch, once nothing is standing on it any more.

    Last of the three, and the only one gated on the others. The checkout that
    was on it has to be gone, which is git's own rule; the remote's copy has
    to be settled, which is this domain's -- an issue is found again by the
    branch and the checkout this host holds, so deleting the branch while a
    remote artifact survives is what makes that artifact unfindable.
    """
    if tip.answer is not ProbeAnswer.CONFIRMED:
        return _unresolved(artifacts, branch, tip, _CLONE)
    if not released:
        log.warning(
            "issue=#%d keeping the local branch %r: a surface ahead of it is "
            "still standing, and this branch is what leads back to it",
            artifacts.issue_number, branch,
        )
        return SurfaceOutcome.FAILED
    return _deleted_local_branch(artifacts, branch, tip.sha)


def _deleted_local_branch(
    artifacts: IssueArtifacts, branch: str, expected: str,
) -> SurfaceOutcome:
    """The ref update that deletes, inside the boundary that owns its failures.

    `update-ref -d` naming the old value rather than `branch -D`, because this
    is the destructive boundary and naming it makes the reading and the
    deletion one step: a branch that moved in between is refused by git, where
    a `branch -D` standing behind the same reading would take whatever it
    found there.

    Lock-held for the reason every ref this clone holds is written under that
    lock: a concurrent `worktree add` on another thread is writing the same
    store, and the two racing leave one of them reporting a failure that is
    nothing but the collision.
    """
    try:
        with locks._target_root_lock(artifacts.spec.target_root):
            deleted = commands._git_hardened(
                "update-ref", "-d", _branch_ref(branch), expected,
                cwd=artifacts.spec.target_root,
            )
    except Exception:
        log.exception(
            "issue=#%d deleting the local branch %r raised",
            artifacts.issue_number, branch,
        )
        return SurfaceOutcome.FAILED
    if deleted.returncode == 0:
        return SurfaceOutcome.CLEANED
    log.warning(
        "issue=#%d local branch %r delete failed: %s",
        artifacts.issue_number, branch, (deleted.stderr or "").strip(),
    )
    return SurfaceOutcome.FAILED


def _unresolved(
    artifacts: IssueArtifacts, branch: str, tip: BranchTip, host: str,
) -> SurfaceOutcome:
    """What a ref that did not resolve leaves the step that was to delete it.

    The two negatives a tip read answers with, spent the way the whole domain
    spends them: a ref that is not there is a deletion that already happened
    and is success, and a ref nobody could read is a question that was never
    put -- which a step whose next move is destroying something must not spend
    as either answer.
    """
    if tip.answer is ProbeAnswer.REFUTED:
        return SurfaceOutcome.ABSENT
    log.warning(
        "issue=#%d keeping %r: %s would not say what it is at",
        artifacts.issue_number, branch, host,
    )
    return SurfaceOutcome.FAILED
