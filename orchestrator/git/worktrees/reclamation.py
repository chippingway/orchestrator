# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Taking down the artifacts one eligible verdict cleared.

The destructive half of the artifact domain, and the only owner in it that
writes anything: ``eligibility`` decides, and this spends what it decided. A
verdict is the whole of the permission -- nothing here re-derives one it was
handed, and one that keeps its candidate is refused before a single read is
taken. The pass that has no verdict, because it starts from a record rather
than a candidate, asks that owner for one: what a record carries is which
branch to go and ask about, never the right to delete it.

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
to delete something. A reading is not enough on its own for the checkout,
whose tree anybody may write in: the removal runs with git's own `index.lock`
and `HEAD.lock` for that checkout held, so no commit can land between the
reading and the removal, and with what the tree is standing on pinned to an
anchor that is created and never overwritten, so anything that landed before
them is kept rather than taken. The one protection a stated expectation does not carry is
git's own refusal to delete a branch some checkout is on -- `update-ref` has
no such refusal where `branch -D` does -- so the worktrees of the clone are
asked, under the lock and immediately before the deletion, whether any of them
is still standing on it.

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

That ordering works while this host still holds something. The shape it
cannot cover is the local artifact that went before the teardown reached it --
a human deleting the branch a moment earlier -- since then there is nothing
left to keep back, and a remote deletion that fails afterwards is a leftover
nothing here names any more. So the deletion is written down in
``obligations`` before the remote is asked anything at all -- the reads are
among the things that fail, and a record written after them is one the
failures needing it never reach -- and let go only once the branch is gone
from the remote; a deletion that could not be written down first is not
attempted at all. Finishing those records is this module's second entry point,
and it needs no candidate: it reads what this host wrote down rather than what
it still holds.

That pass is also the one place here that fetches, and it fetches for the
classification's sake rather than its own. A branch somebody recreated on the
remote from a clone this host has never seen stands on a commit no local
ancestry read can measure, and a read that cannot answer is a retention -- so
the record would be kept and put again every pass, over an answer that does
not change by being asked twice. The commit is brought into this clone before
the record is classified, which puts it within reach without making it
evidence: what a fetch lands is objects and a remote-tracking ref, and every
reading that decides anything still comes from the remote itself.

That is the whole of the retry: nothing is remembered in this process. A
surface that failed is an artifact still on disk, still on the remote, or
named by a record beside it, so the next pass reports the issue again, the
classification proves it again, and this runs again -- across a restart
exactly as within one process.
"""
from __future__ import annotations

import contextlib
import logging
from collections.abc import Mapping
from itertools import chain
from pathlib import Path
from types import MappingProxyType

from orchestrator import config
from orchestrator.git import authentication, commands, locks
from orchestrator.git.worktrees import (
    eligibility,
    evidence,
    obligations,
    paths,
)

# What a teardown is handed -- the candidate, the permission over it, the
# commits that permission cleared, and the answers the reads it retakes come
# back in -- and what it answers with: one entry per place an artifact had to
# be taken from.
from orchestrator.git.worktrees.models import (
    ArtifactReclamation,
    ArtifactSurface,
    ArtifactVerdict,
    BranchTip,
    IssueArtifacts,
    ProbeAnswer,
    ProvenTip,
    SurfaceOutcome,
    SurfaceResult,
)
from orchestrator.github.client import GitHubClient

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

# How `worktree list --porcelain` spells the two things a caller about to
# delete a branch has to tell apart: the checkout that is on it, and the
# registration whose directory is gone from under it.
_ON_BRANCH = "branch"

_PRUNABLE = "prunable"

# What keeps a deletion from travelling down a symbolic ref to whatever it
# names. `update-ref` follows one by default, so a branch made symbolic in the
# store the checkouts share would have the deletion take its target instead.
_NO_DEREF = "--no-deref"

# The exit status `symbolic-ref --quiet` answers with when the ref it was
# asked about is a plain one, or is not there at all. Every other status is a
# reading that established nothing.
_GIT_NOT_SYMBOLIC = 1

# The two lock files git itself takes before it moves a checkout's HEAD or
# writes its index, in the git directory that checkout keeps. Held here for
# the length of a removal, they are what makes the reading before it hold: a
# `commit`, a `checkout`, a `reset`, or an `update-ref HEAD` in that tree
# fails outright while they are ours, so the commit this pass measured is the
# commit the removal takes.
_CHECKOUT_LOCKS = ("index.lock", "HEAD.lock")


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

    What no reading covers is what the tree does next. The lock this runs
    under is this process's own, and the agents and humans who write in a
    checkout are neither: a commit made after the readings and left on no
    branch is clean, is removed without complaint, and is reachable from
    nothing afterwards. So the removal goes through the anchor, which is not a
    reading at all.
    """
    present = _checkout_present(worktree)
    if present is ProbeAnswer.REFUTED:
        return SurfaceOutcome.ABSENT
    if present is ProbeAnswer.UNREADABLE or not _still_cleared(
        artifacts, worktree, proven_sha,
    ):
        return SurfaceOutcome.FAILED
    return _anchored_removal(artifacts, worktree, proven_sha)


def _anchored_removal(
    artifacts: IssueArtifacts, worktree: Path, proven_sha: str | None,
) -> SurfaceOutcome:
    """Remove the checkout with what it is holding pinned first.

    The anchor is taken one process before the removal and read back one
    process after it, which is what turns a race into a report: whatever the
    checkout was standing on at the moment the note was written outlives the
    removal, so a commit somebody made after the readings is preserved rather
    than stranded, and this pass can say that it was not the commit anybody
    cleared.

    An anchor that could not be written stops the removal. What it covers is
    exactly the thing a caller cannot check for afterwards, so a removal that
    ran without one would be a removal nobody could say the cost of.

    The anchor alone would still leave the step between it and the removal,
    which is why git's own locks are held around both. A checkout whose
    `index.lock` and `HEAD.lock` this process holds is one no `commit`,
    `checkout`, `reset`, or `update-ref HEAD` can run in: git takes those two
    before it moves a HEAD or writes an index, and it does not queue for them.
    So the commit the anchor pinned is the commit the removal takes.
    """
    gitdir = _checkout_gitdir(artifacts, worktree)
    if gitdir is None:
        return SurfaceOutcome.FAILED
    with contextlib.ExitStack() as holding:
        held = _held_still(artifacts, gitdir)
        if not held:
            return SurfaceOutcome.FAILED
        holding.callback(_let_go, held)
        return _removal_while_held(artifacts, worktree, proven_sha)


def _checkout_gitdir(
    artifacts: IssueArtifacts, worktree: Path,
) -> Path | None:
    """The git directory this checkout keeps, where its own locks are taken.

    Asked of git rather than assembled, because a linked worktree's is under
    the parent's store and the `.git` at the checkout's root is a file naming
    it. `None` is a reading that established nothing, and a removal that
    cannot find where to hold the tree still does not run.
    """
    located = commands._git_hardened(
        "rev-parse", "--absolute-git-dir", cwd=worktree,
    )
    named = (located.stdout or "").strip()
    if located.returncode != 0 or not named:
        log.warning(
            "issue=#%d keeping the checkout %s: its git directory could not "
            "be named (%s)",
            artifacts.issue_number, worktree, (located.stderr or "").strip(),
        )
        return None
    return Path(named)


def _held_still(
    artifacts: IssueArtifacts, gitdir: Path,
) -> tuple[Path, ...]:
    """Take git's own locks for one checkout, or come back with none.

    Created exclusively, so a lock somebody else is already holding is one
    this refuses rather than steals: a git command running in that tree at
    this moment is exactly the thing the locks are meant to exclude, and
    taking it from under them would corrupt what it is doing.

    Only what was actually taken is reported, so what is given back afterwards
    is only ever this process's own.
    """
    taken: list[Path] = []
    for lock_name in _CHECKOUT_LOCKS:
        lock = gitdir / lock_name
        try:
            lock.touch(exist_ok=False)
        except OSError as busy:
            log.warning(
                "issue=#%d keeping the checkout: %s is already held (%s)",
                artifacts.issue_number, lock, busy,
            )
            _let_go(tuple(taken))
            return ()
        taken.append(lock)
    return tuple(taken)


def _let_go(held: tuple[Path, ...]) -> None:
    """Give back the locks this took, whichever of them are still there.

    A removal that succeeded took the git directory and both locks with it,
    which is the ordinary way they go.
    """
    for lock in held:
        try:
            lock.unlink(missing_ok=True)
        except OSError as refused:
            log.warning("the lock %s could not be given back: %s", lock, refused)


def _removal_while_held(
    artifacts: IssueArtifacts, worktree: Path, proven_sha: str | None,
) -> SurfaceOutcome:
    """Pin what the checkout holds, take it down, and say what came with it."""
    spec = artifacts.spec
    if not obligations._anchor_checkout(
        spec, worktree, artifacts.issue_number,
    ):
        log.warning(
            "issue=#%d keeping the checkout %s: what it is standing on could "
            "not be pinned first", artifacts.issue_number, worktree,
        )
        return SurfaceOutcome.FAILED
    removed = commands._git_hardened(
        "worktree", "remove", str(worktree), cwd=spec.target_root,
    )
    if removed.returncode != 0:
        log.warning(
            "issue=#%d worktree remove of %s failed: %s",
            artifacts.issue_number, worktree, (removed.stderr or "").strip(),
        )
        obligations._discard_anchor(spec, artifacts.issue_number)
        return SurfaceOutcome.FAILED
    return _anchor_settled(artifacts, proven_sha)


def _anchor_settled(
    artifacts: IssueArtifacts, proven_sha: str | None,
) -> SurfaceOutcome:
    """What the removal took, measured against what the verdict cleared.

    Equal is the ordinary answer, and the anchor goes: the commit it pinned is
    the one the classification proved survives its artifact, so nothing here
    is the only thing holding it.

    Anything else is work made before the locks went on, and it is kept under
    the anchor and reported at error. It also stands in the way of every later
    removal for this issue, since an anchor is created and never overwritten:
    what is pinned there is a commit nothing else names, and an operator is
    the one who decides what becomes of it. The checkout is gone by then --
    that is what the anchor exists for -- but the commit is not, and the
    surface coming back failed is what keeps the branch beside it standing, so
    the issue is still one a later pass finds. A commit nobody can name is
    reported the same way: an anchor that would not read back establishes
    nothing about what was taken.
    """
    spec = artifacts.spec
    anchored = obligations._anchored_commit(spec, artifacts.issue_number)
    if anchored and anchored == proven_sha:
        obligations._discard_anchor(spec, artifacts.issue_number)
        return SurfaceOutcome.CLEANED
    log.error(
        "issue=#%d the checkout was on %r rather than the %r this verdict "
        "cleared when it came down; that commit is kept at %s",
        artifacts.issue_number,
        anchored or "a commit nobody could read back",
        proven_sha,
        obligations._anchor_ref(spec, artifacts.issue_number),
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
        remote = _reclaimed_remote_branch(
            artifacts.spec, artifacts.issue_number, branch, cleared_sha,
        )
    if tip.answer is ProbeAnswer.REFUTED and remote is SurfaceOutcome.FAILED:
        _stranded(artifacts, branch)
    return _branch_surfaces(branch, remote, _reclaimed_local_branch(
        artifacts, branch, tip, remote=remote, freed=freed,
    ))


def _stranded(artifacts: IssueArtifacts, branch: str) -> None:
    """Say so when nothing is left to find a branch this could not settle by.

    The one shape this domain cannot make discoverable on its own. The local
    copy went before the teardown reached it, so there is no artifact to keep
    back, and if the record that would have carried it could not be written --
    a ref store refusing a write is one nothing durable can be put in -- then
    nothing here names that branch any more.

    Reported at error rather than warning for exactly that reason: every other
    failure in this pass is one a later pass picks up, and this is the one
    only an operator can. A record that IS there says the opposite, and the
    ledger is asked rather than assumed, since the write and this line are two
    steps and only the first of them knows whether it landed.
    """
    owed = obligations._recorded_obligations(artifacts.spec)
    if owed is not None and any(
        record.subject == branch for record in owed
    ):
        return
    log.error(
        "issue=#%d %r is gone from this clone and was not settled on the "
        "remote, with nothing written down for it: no later pass of this "
        "host will find it", artifacts.issue_number, branch,
    )


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
    spec: config.RepoSpec,
    issue_number: int,
    branch: str,
    cleared_sha: str | None,
) -> SurfaceOutcome:
    """Delete the remote's copy of one branch, or say why it is still there.

    Asked of the remote itself rather than of `refs/remotes/<remote>/<branch>`
    for the reason the classification asks that way: the mirror is a local ref
    in the store every per-issue worktree shares, and this step's next move is
    a deletion on somebody's repository.

    The record goes down before any of that, because the reads are one of the
    things it has to cover. A remote that would not answer and a remote that
    has moved on both end this step with the branch still standing there, and
    by then the local artifacts may already be gone -- so a record written
    only once the remote had confirmed would be a record exactly the failures
    that need it never reach.

    Nothing is written for a branch nothing cleared, and nothing is deleted
    for one either. A record is the note that a deletion of one commit is
    owed, and an artifact no verdict handed a commit for is not one this may
    delete -- which is a different answer from there being nothing there, and
    `_unproven_remote` is where the two are told apart.

    Taken as a commit and a name rather than as a candidate, so the pass that
    reads a record back spends it through exactly these steps.
    """
    if cleared_sha is None:
        return _unproven_remote(spec, issue_number, branch)
    if not obligations._record_obligation(spec, branch, cleared_sha):
        log.warning(
            "issue=#%d keeping %r on the remote: what this host would owe "
            "afterwards could not be written down first",
            issue_number, branch,
        )
        return SurfaceOutcome.FAILED
    return _recorded_deletion(spec, issue_number, branch, cleared_sha)


def _unproven_remote(
    spec: config.RepoSpec, issue_number: int, branch: str,
) -> SurfaceOutcome:
    """What is left on the remote for a branch nothing cleared a commit for.

    The classification clears a commit for every branch it finds on either
    host, so no commit means it found this one on neither -- and a remote with
    nothing under that name is a surface with nothing to reclaim, which is the
    success every other absence in this domain is. Refusing it instead would
    leave a candidate whose artifacts are all demonstrably gone reported as a
    failure no later pass could settle, since there is nothing left anywhere
    for one to find.

    Anything else is a leftover this pass may not touch and must not lose. A
    branch that is back was published after the proof was taken, so what is
    under that name is work nobody adjudicated; a remote that would not answer
    has established nothing at all. Neither is deleted, and both are written
    down, because by here the local copy is gone as well and a reminder is the
    only thing that would lead a later pass to either.
    """
    published = evidence._published_tip(spec, branch)
    if published.answer is ProbeAnswer.REFUTED:
        return SurfaceOutcome.ABSENT
    return _reminded(spec, issue_number, branch, published)


def _reminded(
    spec: config.RepoSpec,
    issue_number: int,
    branch: str,
    published: BranchTip,
) -> SurfaceOutcome:
    """Note that one branch is unfinished business, and keep it.

    A reminder rather than an obligation, because no commit was cleared here
    and a record naming one would be saying otherwise. What it carries is the
    name; the pass that reads it back asks the classification for everything
    else, exactly as it does for a record written after a proof.

    Self-clearing, which is what makes it safe to write on a reading that
    established nothing: the first later pass that finds the branch gone from
    the remote lets it go again.

    A reminder that could not be written is not answered here. The branch step
    above reports what is left of this issue, and it is the one that knows
    whether anything at all still names it.
    """
    obligations._remind(spec, branch)
    log.warning(
        "issue=#%d keeping %r on the remote (%s), with nothing cleared for "
        "it: written down to be asked about again",
        issue_number,
        branch,
        published.sha or "the remote would not say what it is at",
    )
    return SurfaceOutcome.FAILED


def _recorded_deletion(
    spec: config.RepoSpec, issue_number: int, branch: str, cleared_sha: str,
) -> SurfaceOutcome:
    """What the remote says about one branch, and the deletion that allows.

    Everything here runs with the record already down, so each way out is one
    a later pass can pick up. Only two of them let it go: the branch is gone
    from the remote, or this is what took it.

    A branch the remote does not carry is the ordinary terminal shape -- a
    merged pull request's head branch is deleted there -- and it is success.

    A branch the remote carries at some other commit is nobody's to delete on
    the strength of what was cleared, and it keeps the record standing.
    Letting one go there would be quietest exactly where quiet is wrong: the
    branch is still on the remote, this host may have nothing left that names
    its issue, and a pass that dropped the record would come back empty about
    a leftover that is still there. The record is not stale either -- what it
    says is which commit this host was cleared to delete, and that stays true
    however far the remote moves. The branch going is what settles it.
    """
    published = evidence._published_tip(spec, branch)
    if published.answer is ProbeAnswer.REFUTED:
        return _discharged(spec, branch, SurfaceOutcome.ABSENT)
    if published.answer is ProbeAnswer.UNREADABLE:
        return _unresolved(issue_number, branch, published, _REMOTE)
    if published.sha != cleared_sha:
        log.warning(
            "issue=#%d keeping %r on the remote: it carries %r where what was "
            "cleared is %r", issue_number, branch, published.sha, cleared_sha,
        )
        return SurfaceOutcome.FAILED
    if _deleted_remote_branch(spec, issue_number, branch, cleared_sha):
        return _discharged(spec, branch, SurfaceOutcome.CLEANED)
    return _refused_push(spec, issue_number, branch)


def _refused_push(
    spec: config.RepoSpec, issue_number: int, branch: str,
) -> SurfaceOutcome:
    """What a refused deletion left on the remote, asked a second time.

    The lease is refused for a ref that MOVED and for one that WENT alike --
    both are "not the commit you named" -- and only the first of those is a
    failure. Somebody else deleting the branch between the reading and the
    push is the deletion this was for happening without it, so it is the
    success it looks like from every other angle, and the record over it has
    nothing left to cover.

    The same second reading the local deletion takes, for the same reason: a
    surface reported failed over an artifact that is already gone is one no
    later pass can settle, and here there may be nothing local left to find
    the issue by at all.
    """
    published = evidence._published_tip(spec, branch)
    if published.answer is ProbeAnswer.REFUTED:
        return _discharged(spec, branch, SurfaceOutcome.ABSENT)
    log.warning(
        "issue=#%d the remote would not let go of %r", issue_number, branch,
    )
    return SurfaceOutcome.FAILED


def _deleted_remote_branch(
    spec: config.RepoSpec, issue_number: int, branch: str, expected: str,
) -> bool:
    """The push that deletes, inside the boundary that owns its failures.

    Pinned to the commit just read, which is the commit that was cleared: the
    same lease the immutable snapshot namespace is reclaimed under. A branch
    somebody pushed to between the reading and this push fails the lease
    instead of being overwritten by it, which is the only revalidation
    available on a host this process does not hold a lock on.
    """
    try:
        return authentication._delete_remote_ref(
            spec, spec.target_root, ref=_branch_ref(branch), expected=expected,
        )
    except Exception:
        log.exception(
            "issue=#%d deleting the remote branch %r raised",
            issue_number, branch,
        )
        return False


def _discharged(
    spec: config.RepoSpec, branch: str, outcome: SurfaceOutcome,
) -> SurfaceOutcome:
    """Let go of the record for a deletion nobody owes any more, and answer.

    Called on the two answers that end the matter: the branch went, or it was
    already gone. Both say the remote has nothing of this issue's left under
    that name, so a record kept over either is one every later pass would
    spend a round trip on to reach the same answer.

    Nothing else discharges. A record is the only thing that leads a later
    pass back to a branch this host may no longer name, so it outlives every
    answer short of the branch being gone.

    A record that would not go away does not change the answer. What it
    covered is settled either way, and the pass after this one asks the remote
    once more, finds nothing owed, and lets it go then.
    """
    obligations._discharge_obligation(spec, branch)
    return outcome


def _reclaim_recorded_remotes(
    gh: GitHubClient, spec: config.RepoSpec,
) -> tuple[SurfaceResult, ...]:
    """Finish the remote deletions this host wrote down and did not complete.

    The pass that needs no candidate. What the scan in ``inventory`` reports is
    what this host still holds, and the leftover this exists for is the one
    with nothing left to hold: a remote branch whose local artifacts went
    before the deletion that was to follow them. So this reads what was
    written down rather than what is on disk, which is what makes the retry
    survive a restart rather than a tick -- and it takes a client, because
    what a record cannot carry is the permission.

    Every record is put back through the steps the teardown that wrote it was
    on, the classification included -- because a record is a note about a
    moment too, and the moment has passed.

    Only this repository's own records are read: several `REPOS` entries may
    share a clone and so this ledger, and a branch another of them published
    has a remote this one knows nothing about. Inside that namespace, a name
    no derivation here produces is passed over rather than reported -- a ref
    somebody wrote by hand is nobody's to spend.
    """
    recorded = obligations._recorded_obligations(spec)
    if recorded is None:
        return (SurfaceResult(
            ArtifactSurface.REMOTE_BRANCH,
            obligations.RECLAIM_NAMESPACE,
            SurfaceOutcome.FAILED,
        ),)
    settled = []
    for owed in recorded:
        issue_number = _owed_issue(spec, owed.subject)
        if issue_number is not None:
            settled.append(SurfaceResult(
                ArtifactSurface.REMOTE_BRANCH,
                owed.subject,
                _reclaimed_record(gh, spec, issue_number, owed),
            ))
    return tuple(settled)


def _reclaimed_record(
    gh: GitHubClient,
    spec: config.RepoSpec,
    issue_number: int,
    owed: ProvenTip,
) -> SurfaceOutcome:
    """Spend one record, once the classification clears its branch again.

    A record is a reminder, never a permission. It lives in the ref store the
    per-issue checkouts share, which is a store the agents this orchestrator
    runs can write: a name under this namespace and a commit beside it are
    both things one of them can put there, so a pass that took a record as
    proof would authenticate-delete a branch on the strength of something the
    work being torn down wrote. What a record says is which branch to go and
    ask about. The answer comes from where a candidate's does -- the issue has
    ended, no pull request is standing on the branch, and the commit survives
    the deletion -- and it is asked again here rather than assumed, because
    nothing this pass has was established by anybody but the last one.

    A record that outlives every reason to spend it is let go rather than
    carried: the point of one is a leftover somebody can still act on.

    The remote is asked before any of that, because a branch that is no longer
    there needs no permission: nothing is deleted, so nothing has to be
    cleared, and a record kept over it would be one every later pass spent a
    classification on to reach the same answer. It is also the one answer no
    reading of this host can overturn -- a local copy somebody recreated with
    work of their own would otherwise keep a settled remote unsettled forever.

    What is spent is the commit the fresh verdict clears, not the one the
    record names. The ledger says which branch to go and ask about; the answer
    is about that branch as it is now. A branch whose work moved on after the
    record was written and has since been accounted for is one this may still
    reclaim, and refusing it because an older note named an older commit would
    leave a leftover nothing could ever clean up.
    """
    published = evidence._published_tip(spec, owed.subject)
    if published.answer is ProbeAnswer.REFUTED:
        return _discharged(spec, owed.subject, SurfaceOutcome.ABSENT)
    _within_reach(spec, issue_number, owed.subject, published)
    verdict = eligibility._classify_artifacts(gh, IssueArtifacts(
        spec=spec,
        issue_number=issue_number,
        worktree=None,
        branches=(owed.subject,),
    ))
    cleared = _cleared_tip(verdict, owed.subject)
    if cleared is None:
        log.warning(
            "issue=#%d not spending the record for %r: the classification "
            "clears no commit for it (%s)",
            issue_number,
            owed.subject,
            ", ".join(sorted(kept.reason for kept in verdict.retentions)),
        )
        return SurfaceOutcome.FAILED
    return _reclaimed_remote_branch(
        spec, issue_number, owed.subject, cleared.sha,
    )


def _within_reach(
    spec: config.RepoSpec,
    issue_number: int,
    branch: str,
    published: BranchTip,
) -> None:
    """Put the commit the remote is standing on where a proof can read it.

    The one thing the classification cannot do for itself. It measures a tip
    against the base by ancestry, and ancestry is a question about objects
    this clone has: a branch somebody recreated on the remote from a clone
    this host has never fetched leaves that read unable to answer at all, and
    an unanswerable read is a retention. So the record would be kept, the
    branch would be asked about again next pass, and the pull request that
    safely accounts for the commit would never be reached -- forever, since
    nothing about a remote-only commit changes by being asked twice.

    Fetched here rather than in the classification, which is a pass that
    reads and decides and writes nothing anywhere. This one already writes,
    and what it takes is the ordinary authenticated branch fetch every other
    caller in this orchestrator takes: the objects land in the store and the
    remote-tracking ref beside them, neither of which is evidence -- every
    reading that decides anything still comes from the remote itself.

    Only when there is something to fetch, and only for a branch this
    repository publishes this issue under, which is what the caller
    established before it got here. A commit this clone already carries costs
    one local read and no round trip.

    Nothing is answered. A fetch that failed leaves the classification exactly
    where it would have been without one, which is a retention that keeps the
    record -- so the leftover stays discoverable and the pass after this one
    tries again.
    """
    if published.answer is not ProbeAnswer.CONFIRMED:
        return
    if evidence._carries_commit(spec, published.sha) is ProbeAnswer.CONFIRMED:
        return
    try:
        fetched = authentication._authed_target_fetch(spec, branch)
    except Exception:
        log.exception(
            "issue=#%d fetching %r before classifying its record raised",
            issue_number, branch,
        )
        return
    if fetched.returncode != 0:
        log.warning(
            "issue=#%d %r is at %r on the remote and nowhere in this clone, "
            "and the fetch that would bring it within reach failed: %s",
            issue_number,
            branch,
            published.sha,
            (fetched.stderr or "").strip(),
        )


def _cleared_tip(verdict: ArtifactVerdict, branch: str) -> ProvenTip | None:
    """The commit one fresh classification cleared for one branch, if any.

    None covers both ways there is nothing to spend: a verdict that keeps the
    candidate carries no proof at all, and an eligible one can clear nothing
    for a branch it found on neither host. A caller holding a record has to
    treat them alike -- neither is permission to delete anything -- and the
    reason they differ is in the retentions it reports.
    """
    return next(
        (tip for tip in verdict.proven if tip.subject == branch), None,
    )


def _owed_issue(spec: config.RepoSpec, branch: str) -> int | None:
    """The issue one recorded branch belongs to, when this repository owns it.

    The ownership policy the teardown applies to a verdict's branches, applied
    to a name that came off a ref store instead: the issue number is read back
    out of the name, and the name has to be one of the two this repository
    publishes that issue under. Everything else answers None, and a caller
    that has to delete something on a remote may not act on any of them.

    Which repository is asking is settled before this by where the record was
    read from -- the ledger is written under each repository's own segment,
    so the flat legacy name every entry on a shared clone derives is never one
    entry reading another's record. What is left for this to catch is a name
    inside that namespace which no derivation here produces.
    """
    issue_number = paths._issue_segment_number(
        branch.rsplit("/", 1)[-1],
    )
    if issue_number is None:
        return None
    if branch not in paths._issue_branch_names(spec, issue_number):
        return None
    return issue_number


def _reclaimed_local_branch(
    artifacts: IssueArtifacts,
    branch: str,
    tip: BranchTip,
    *,
    remote: SurfaceOutcome,
    freed: bool,
) -> SurfaceOutcome:
    """Delete one local branch, once nothing is standing on it any more.

    Last of the three, and the only one gated on the others. The remote's copy
    of this branch has to have settled, which is this domain's rule -- an
    issue is found again by the branch and the checkout this host holds, so
    letting go of the branch while a remote artifact survives is what makes
    that artifact unfindable. The checkout that was on it has to be gone too,
    which is git's rule and this one's both.

    What this branch's own read established is answered before either gate,
    because it is about the branch rather than about what is standing beside
    it: a ref nobody could read is a refusal, and a ref already gone is a
    deletion that has happened. What a failed remote step then needs is
    carried by the record that step wrote, not by a surface reported as though
    the branch were still here to find.
    """
    if tip.answer is ProbeAnswer.UNREADABLE:
        return _unresolved(artifacts.issue_number, branch, tip, _CLONE)
    if tip.answer is ProbeAnswer.REFUTED:
        return SurfaceOutcome.ABSENT
    if remote is SurfaceOutcome.FAILED:
        log.warning(
            "issue=#%d keeping the local branch %r: its copy on the remote is "
            "still standing, and this branch is what leads back to it",
            artifacts.issue_number, branch,
        )
        return SurfaceOutcome.FAILED
    if not freed:
        log.warning(
            "issue=#%d keeping the local branch %r: the checkout that stood "
            "on it is still there", artifacts.issue_number, branch,
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

    The one thing naming the old value does not buy is what `branch -D` gets
    for free: git refuses that one while a checkout is on the branch, and
    `update-ref` deletes it out from under a live tree and leaves its HEAD
    naming nothing. So the worktrees are asked here, inside the lock and with
    the deletion, rather than left to the reading of this issue's own checkout
    that the pass opened with -- a tree added or moved onto this branch since
    then is a tree that reading never saw.

    Nor does the old value say WHICH ref it was read through. A branch that is
    a symbolic ref resolves to whatever it names, so the proof would be about
    that other ref's commit and the deletion, left to follow it, would take
    that other ref: `refs/heads/main` deleted while this issue's name is left
    dangling. Both halves are answered here -- the ref is refused when it is
    symbolic, and the update says so as well, so a ref made symbolic between
    the two cannot travel either.

    Lock-held for that and for the reason every ref this clone holds is
    written under that lock: a concurrent `worktree add` on another thread is
    writing the same store, and the two racing leave one of them reporting a
    failure that is nothing but the collision.
    """
    try:
        with locks._target_root_lock(artifacts.spec.target_root):
            if _checkouts_holding(artifacts, branch) or _symbolic_branch(
                artifacts, branch,
            ):
                return SurfaceOutcome.FAILED
            deleted = commands._git_hardened(
                "update-ref", "-d", _NO_DEREF, _branch_ref(branch), expected,
                cwd=artifacts.spec.target_root,
            )
            if deleted.returncode == 0:
                return SurfaceOutcome.CLEANED
            return _refused_delete(
                artifacts, branch, (deleted.stderr or "").strip(),
            )
    except Exception:
        log.exception(
            "issue=#%d deleting the local branch %r raised",
            artifacts.issue_number, branch,
        )
        return SurfaceOutcome.FAILED


def _refused_delete(
    artifacts: IssueArtifacts, branch: str, complaint: str,
) -> SurfaceOutcome:
    """What a refused deletion left, once the ref is asked about again.

    Stating the old value makes git refuse two things that are nothing alike.
    A branch that MOVED is work somebody made and this must not take, which is
    the whole reason the value is stated. A branch that WENT is the deletion
    this was for, done by somebody else in the window between the reading and
    the update -- and git refuses that one too, because the value it was told
    to expect is not there any more.

    Reported apart for what the second costs: the branch is what a later scan
    would have found the candidate by, so an issue reported as failed over an
    artifact that is already gone is one nothing will ever settle. Asked again
    under the same lock, so what answers is the ref store this deletion just
    ran against rather than one another thread has since moved on.
    """
    tip = evidence._local_branch_tip(artifacts.spec, branch)
    if tip.answer is ProbeAnswer.REFUTED:
        return SurfaceOutcome.ABSENT
    log.warning(
        "issue=#%d local branch %r delete failed: %s",
        artifacts.issue_number, branch, complaint,
    )
    return SurfaceOutcome.FAILED


def _symbolic_branch(artifacts: IssueArtifacts, branch: str) -> bool:
    """Whether this issue's branch is a symbolic ref rather than a branch.

    Nothing this orchestrator does makes one: a branch it publishes is created
    by `worktree add` or by an update naming a commit. What a symbolic one
    would be is a name in the store the checkouts share pointed at another
    ref -- and every reading behind the proof resolves through it, so what was
    cleared is that other ref's commit and not anything this name holds.

    Fail-closed, like every read at this boundary: `symbolic-ref --quiet`
    exits 1 for a ref that is not symbolic and for one that is not there, and
    anything else is a reading that established nothing about what deleting
    this name would take.
    """
    named = commands._git_hardened(
        "symbolic-ref", "--quiet", _branch_ref(branch),
        cwd=artifacts.spec.target_root,
    )
    if named.returncode == _GIT_NOT_SYMBOLIC:
        return False
    log.warning(
        "issue=#%d keeping the local branch %r: it is not a branch this "
        "orchestrator would have made (%s)",
        artifacts.issue_number, branch, (named.stdout or "").strip(),
    )
    return True


def _checkouts_holding(artifacts: IssueArtifacts, branch: str) -> bool:
    """Whether a live checkout of this clone is still standing on `branch`.

    The refusal `update-ref` does not make for itself. Every worktree of the
    clone is asked rather than only the path this issue's own checkout belongs
    at, because what a dangling HEAD costs does not depend on who made the
    tree that carries it.

    A worktree git reports as prunable is not one of them. Its registration
    outlived the directory it names, so nothing is standing on the branch and
    holding it back would leave a candidate that can never settle -- a
    checkout somebody removed by hand would keep its branch forever.

    Fail-closed on a listing that could not be taken: a deletion this refuses
    is found again on the next pass, and one it allows on the strength of an
    answer nobody gave is not.
    """
    listed = commands._git_hardened(
        "worktree", "list", "--porcelain", cwd=artifacts.spec.target_root,
    )
    if listed.returncode != 0:
        log.warning(
            "issue=#%d keeping %r: the worktrees of %s would not be listed: "
            "%s",
            artifacts.issue_number,
            branch,
            artifacts.spec.target_root,
            (listed.stderr or "").strip(),
        )
        return True
    holding = any(
        _standing_on(entry, branch)
        for entry in (listed.stdout or "").split("\n\n")
    )
    if holding:
        log.warning(
            "issue=#%d keeping the local branch %r: a checkout of %s is "
            "standing on it",
            artifacts.issue_number, branch, artifacts.spec.target_root,
        )
    return holding


def _standing_on(entry: str, branch: str) -> bool:
    """Whether one `worktree list` entry is a live checkout of `branch`."""
    reported = entry.splitlines()
    if any(line.startswith(_PRUNABLE) for line in reported):
        return False
    return f"{_ON_BRANCH} {_branch_ref(branch)}" in reported


def _unresolved(
    issue_number: int, branch: str, tip: BranchTip, host: str,
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
        issue_number, branch, host,
    )
    return SurfaceOutcome.FAILED
