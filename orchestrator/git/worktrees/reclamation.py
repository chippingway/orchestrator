# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Taking down the checkout one eligible verdict cleared.

The destructive half of the artifact domain, and the only owner in it that
destroys anything: ``eligibility`` decides, and this spends what it decided. A
verdict is the whole of the permission -- nothing here re-derives one it was
handed, and one that keeps its candidate is refused before a single read is
taken.

What the verdict established is established again at the boundary it is about
to be spent at, because a proof is a statement about a moment. Between the
classification and the teardown an agent can write in the tree and a human can
commit onto the branch under its HEAD, so the checkout is proved to be this
issue's own, carrying nothing loose, and standing on the commit that was
cleared before it is removed.

Nothing is forced. The removal runs without `--force`, so the worst this can
do to work nobody adjudicated is fail to delete something. A reading is not
enough on its own for a tree anybody may write in: the removal runs with git's
own `index.lock` and `HEAD.lock` for that checkout held, so no commit can land
between the reading and the removal, and with what the tree is standing on
pinned to an anchor that is created and never overwritten, so anything that
landed before them is kept rather than taken. What an anchor of that kind
cannot say for itself is whether it is holding work or is merely the note a
stopped pass left behind, so the pass after one reads it: pinning the commit
that pass's own verdict cleared, it is spent and taken again, and pinning
anything else it goes on refusing every removal for that issue.

What the removal is aimed by is not the path it is handed either. That path
only selects a registration, and what comes down is the tree the registration
names -- so that file is held for the length of a removal as well: opened
without following, refused unless it is a regular file naming this checkout's
own tree, and pinned by taking the write bits off the object rather than off
the name.

**Absent is success.** A checkout already gone is the ordinary shape of a
second pass, and reporting it as a failure would keep an issue in a report
forever over an artifact nobody can find.

That is the whole of the retry: nothing is remembered in this process. A
surface that failed is an artifact still on disk, so the next pass reports the
issue again, the classification proves it again, and this runs again -- across
a restart exactly as within one process.
"""
from __future__ import annotations

import contextlib
import logging
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from stat import S_ISDIR, S_ISREG
from types import MappingProxyType

from orchestrator import config
from orchestrator.git import commands, locks
from orchestrator.git.worktrees import evidence, obligations, paths

# What a teardown is handed -- the candidate, the permission over it, the
# commits that permission cleared, and the answers the reads it retakes come
# back in -- and what it answers with: one entry per place an artifact had to
# be taken from.
from orchestrator.git.worktrees.models import (
    ArtifactReclamation,
    ArtifactSurface,
    ArtifactVerdict,
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

# What a branch is called when it is named to git in full, which is how the
# lock taken for the branch under a checkout's HEAD is spelled.
_BRANCH_REF_PREFIX = "refs/heads/"

# The two lock files git itself takes before it moves a checkout's HEAD or
# writes its index, in the git directory that checkout keeps. Held here for
# the length of a removal, they are what makes the reading before it hold: a
# `commit`, a `checkout`, a `reset`, or an `update-ref HEAD` in that tree
# fails outright while they are ours, so the commit this pass measured is the
# commit the removal takes.
_CHECKOUT_LOCKS = ("index.lock", "HEAD.lock")

# What git calls the lock file it takes before it writes one ref, appended to
# the ref's own path under the store the clone shares. Held for the branch a
# checkout's HEAD is on, it is what stops that branch moving under the anchor
# -- an `update-ref` on it answers to neither of the two above.
_REF_LOCK = ".lock"

# What this pass writes into every lock it takes, beside the process that took
# it. Git writes an index, a ref line, or an object id into these and never
# this, so the mark is what lets a later pass tell a lock some command is
# holding right now from one a killed pass left behind.
_LOCK_MARK = "orchestrator-reclaim"

# The file in a checkout's administrative directory that says where that
# checkout is, and the bits taken off it while one comes down. It is what
# `worktree remove` reads to decide what to delete and what `worktree repair`
# rewrites, and nothing locks it -- so the mode is the hold.
_REGISTRATION = "gitdir"

_WRITABLE = 0o222

# What a registration always carries when git wrote it, and what one is given
# back regardless: a mode without it is this host's own hold, left by a pass
# that did not come back to release it.
_OWNER_WRITE = 0o200

# How that file is opened: read-only and refusing to follow, so a link left
# at the name fails the open outright rather than handing this pass somebody
# else's file to read, to hold, and to change the mode of.
_UNFOLLOWED = os.O_RDONLY | os.O_NOFOLLOW

# How much of it is read. A registration is one path and a newline, so
# anything past this is not one -- and the read is bounded because the file is
# one an agent can write.
_REGISTRATION_LIMIT = 4096


def _branch_ref(branch: str) -> str:
    """The fully-qualified ref one of this issue's branch names spells."""
    return f"{_BRANCH_REF_PREFIX}{branch}"


def _reclaim_artifacts(verdict: ArtifactVerdict) -> ArtifactReclamation:
    """Take this issue's checkout down, on the strength of one verdict.

    The verdict is the permission and the proof both, and it is taken as
    handed over: a candidate this pass may not touch is one whose reads have
    already been paid for, and putting them again here would be a second
    opinion nobody asked for -- one that can disagree with the first.

    The proof is read by subject rather than by position, because a verdict
    carries one entry per artifact it cleared and the checkout is only one of
    them. A checkout the verdict cleared no commit for is one the removal
    refuses on its own: what it is measured against is then nothing at all.
    """
    artifacts = verdict.artifacts
    if not verdict.eligible:
        log.warning(
            "issue=#%d refusing to reclaim: this verdict keeps the candidate",
            artifacts.issue_number,
        )
        return ArtifactReclamation(artifacts, _untouched(artifacts))
    proven = MappingProxyType({tip.subject: tip.sha for tip in verdict.proven})
    return _reported(artifacts, _reclaimed_checkout(artifacts, proven))


def _reported(
    artifacts: IssueArtifacts, surfaces: tuple[SurfaceResult, ...],
) -> ArtifactReclamation:
    """The teardown's answer, with what it destroyed said out loud once.

    Said here rather than at each step, and said at all rather than left to
    the caller: a deletion is the one thing in this domain that cannot be
    reconstructed afterwards, so an operator asking later what became of a
    checkout finds the answer in the log whether or not whoever asked for the
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
    surface is named rather than the answer left empty, because an empty
    report is what a candidate with nothing left to reclaim gets -- and this
    one has everything left.
    """
    if artifacts.worktree is None:
        return ()
    return (SurfaceResult(
        ArtifactSurface.WORKTREE,
        str(artifacts.worktree),
        SurfaceOutcome.FAILED,
    ),)


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

    Those two are about the tree's own HEAD, and a checkout's HEAD is a
    symbolic ref: what it stands on is whatever the branch under it stands on,
    and an `update-ref refs/heads/<branch>` moves that without going near
    either lock. So the lock git takes for the branch itself is held too, and
    it is the one that makes the sentence above true -- with it, the commit
    the anchor pinned is the commit the removal takes.
    """
    gitdir = _checkout_gitdir(artifacts, worktree)
    if gitdir is None:
        return SurfaceOutcome.FAILED
    with contextlib.ExitStack() as holding:
        pinned = _everything_held(artifacts, worktree, gitdir, holding)
        if pinned is None:
            return SurfaceOutcome.FAILED
        return _removal_while_held(
            artifacts, worktree, proven_sha, gitdir, pinned,
        )


def _everything_held(
    artifacts: IssueArtifacts,
    worktree: Path,
    gitdir: Path,
    holding: contextlib.ExitStack,
) -> int | None:
    """Take every hold one removal runs under, or come back with none.

    Git's own locks for the tree and the branch under its HEAD, and then the
    registration the removal will be aimed by. Each is given back through the
    stack the caller opened, so a hold taken is a hold released however this
    ends -- and the one thing handed back is the descriptor the last of them
    is pinned by, since the readings before the removal have to be able to ask
    whether the name still means it.
    """
    held = _held_still(artifacts, worktree, gitdir)
    if not held:
        return None
    holding.callback(_let_go, held)
    registration = _registration_held(artifacts, gitdir, worktree)
    if registration is None:
        return None
    pinned, was = registration
    holding.callback(_thawed, pinned, was)
    return pinned


def _registration_held(
    artifacts: IssueArtifacts, gitdir: Path, worktree: Path,
) -> tuple[int, int] | None:
    """Take hold of the file this removal will be aimed by, or refuse.

    What `worktree remove` deletes is not the path it is handed. That path
    only selects a registration, and what comes down is the path the
    registration names -- so the one thing deciding where the destruction
    lands is a file in the administrative directory, and `worktree repair` is
    a single command that rewrites it.

    Opened without following, which is the first of the two things this is
    for. A link left at that name would have every reading here answer about
    somebody else's file and every write land on it, so a link is not read
    around -- it is refused, and the removal with it.

    Held by a descriptor rather than by a name, which is the second. What the
    write bits come off is the object opened here and never whatever the name
    means by then, and what they go back onto is that same object however the
    name has been rearranged since.

    `None` for anything that is not this checkout's own registration, and for
    every reading that could not be taken: a removal aimed by a file this pass
    cannot account for is aimed at nothing in particular.
    """
    registration = gitdir / _REGISTRATION
    try:
        opened = os.open(registration, _UNFOLLOWED)
    except OSError as refused:
        log.warning(
            "issue=#%d keeping the checkout: %s would not open as a file of "
            "its own (%s)", artifacts.issue_number, registration, refused,
        )
        return None
    was = _registration_pinned(artifacts, opened, worktree)
    if was is None:
        os.close(opened)
        return None
    return opened, was


def _registration_pinned(
    artifacts: IssueArtifacts, pinned: int, worktree: Path,
) -> int | None:
    """Whether what was opened aims at this checkout, and its mode if it does.

    A regular file -- a fifo or a directory at that name is not a registration
    and not something to take the write bits off -- naming this checkout's own
    `.git`, which is what says the removal about to run is aimed here rather
    than at a tree somebody repaired it onto. Compared as filesystem objects
    for the reason every path comparison here is: the spellings differ
    honestly under a worktrees root that sits below a link of its own.

    Then the write bits come off, which is what a `repair` fails on: it
    rewrites this file in place, and a file it cannot open for writing leaves
    the registration naming what it named.
    """
    try:
        held, named = _registration_read(pinned)
    except (OSError, ValueError) as unread:
        log.warning(
            "issue=#%d keeping the checkout %s: its registration could not be "
            "read (%s)", artifacts.issue_number, worktree, unread,
        )
        return None
    if not S_ISREG(held.st_mode) or not _aims_here(worktree, named):
        log.warning(
            "issue=#%d keeping the checkout %s: what is registered for it "
            "names %r", artifacts.issue_number, worktree, named.strip(),
        )
        return None
    return _mode_taken_off(artifacts, pinned, held.st_mode)


def _registration_read(pinned: int) -> tuple[os.stat_result, str]:
    """What was opened, and what it says, in one reading of the descriptor."""
    return os.fstat(pinned), os.read(pinned, _REGISTRATION_LIMIT).decode()


def _aims_here(worktree: Path, named: str) -> bool:
    """Whether one registration's contents name this checkout's own tree."""
    inside = named.strip()
    return bool(inside) and _one_directory(worktree, Path(inside).parent)


def _mode_taken_off(
    artifacts: IssueArtifacts, pinned: int, was: int,
) -> int | None:
    """Take the write bits off the object held open, and answer its mode."""
    try:
        os.fchmod(pinned, was & ~_WRITABLE)
    except OSError as refused:
        log.warning(
            "issue=#%d keeping the checkout: its registration could not be "
            "held still (%s)", artifacts.issue_number, refused,
        )
        return None
    return was


def _thawed(pinned: int, was: int) -> None:
    """Give the registration the mode it had back, and let the handle go.

    On the object rather than on the name, so a removal that took the whole
    administrative directory with it -- the ordinary way this ends -- is one
    where the mode goes back onto something nothing names any more, which
    costs nothing and cannot reach anybody else's file.

    Given back writable whatever was found, because what a pass killed between
    the hold and this leaves behind is exactly a registration with its write
    bits off -- and a later pass that restored what it found would make that
    leftover permanent, and `worktree repair` and `worktree move` for that
    checkout along with it. Git writes this file owner-writable; a mode
    without that bit is this host's own leftover rather than anybody's choice.
    """
    try:
        os.fchmod(pinned, was | _OWNER_WRITE)
    except OSError as refused:
        log.warning("a registration's mode could not go back: %s", refused)
    finally:
        os.close(pinned)


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
    artifacts: IssueArtifacts, worktree: Path, gitdir: Path,
) -> tuple[Path, ...]:
    """Take git's own locks for one checkout, or come back with none.

    Created exclusively, so a lock somebody else is already holding is one
    this refuses rather than steals: a git command running in that tree at
    this moment is exactly the thing the locks are meant to exclude, and
    taking it from under them would corrupt what it is doing.

    Only what was actually taken is reported, so what is given back afterwards
    is only ever this process's own.
    """
    locked = _checkout_locks(artifacts, worktree, gitdir)
    if locked is None:
        return ()
    taken: list[Path] = []
    for lock in locked:
        if not _taken_once(artifacts, lock):
            _let_go(tuple(taken))
            return ()
        taken.append(lock)
    return tuple(taken)


def _taken_once(artifacts: IssueArtifacts, lock: Path) -> bool:
    """Take one lock for this process, or say why it stays somebody else's.

    A lock already there is refused rather than stolen: a git command running
    in that tree at this moment is exactly what these exclude, and taking one
    from under it would corrupt what it is doing.

    The one exception is this host's own leftover. These are created by this
    pass and given back by it, so a pass killed between the two leaves a file
    nothing will ever remove -- and every later pass would read it as a
    command still running and refuse the cleanup for good. What this host
    wrote is written inside the lock, so its own leftover is a thing it can
    recognise; anything it cannot is left alone.
    """
    if _lock_created(lock):
        return True
    if not _left_behind(lock):
        log.warning(
            "issue=#%d keeping the checkout: %s is already held",
            artifacts.issue_number, lock,
        )
        return False
    log.warning(
        "issue=#%d %s was left behind by a pass that did not come back, and "
        "is taken again", artifacts.issue_number, lock,
    )
    _let_go((lock,))
    return _lock_created(lock)


def _lock_created(lock: Path) -> bool:
    """Create one lock file for this process alone, marked as this host's.

    The mark is what a later pass reads to tell this host's own leftover from
    a lock some git command is holding right now: git writes its own content
    into each of these -- an index, a ref line, an object id -- and never
    this.

    Room is made for it first, because a ref that has been packed away leaves
    none: the loose file under `refs/heads/` is what `pack-refs` removes, and
    the directories above it go with it. Git makes the same room when it takes
    the same lock, and an empty one it finds instead is one it prunes. A room
    that could not be made is not answered here -- the creation that follows
    fails on its own and says so.
    """
    with contextlib.suppress(OSError):
        lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock.open("x", encoding="utf-8") as taking:
            taking.write(f"{_LOCK_MARK} {os.getpid()}\n")
    except OSError:
        return False
    return True


def _left_behind(lock: Path) -> bool:
    """Whether a lock already there is this host's, from a pass that stopped.

    Two things have to hold, and neither is enough on its own. The mark says
    the file is one this orchestrator wrote rather than one git is holding,
    and the process it names has to be gone -- a sibling pass on the same
    clone being exactly what a lock is for.

    Everything else is left alone: a file this cannot read, a mark it does not
    know, a process still running, and one this host may not signal, which is
    somebody else's however it came by that number.
    """
    named = _lock_holder(lock)
    return named is not None and not _process_alive(named)


def _lock_holder(lock: Path) -> int | None:
    """The process one of this host's own locks names, if it is one of them."""
    try:
        written = lock.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    marked, _sep, named = written.partition(" ")
    if marked != _LOCK_MARK or not named.strip().isdigit():
        return None
    return int(named) or None


def _process_alive(named: int) -> bool:
    """Whether one process id still names something running on this host."""
    try:
        os.kill(named, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _checkout_locks(
    artifacts: IssueArtifacts, worktree: Path, gitdir: Path,
) -> tuple[Path, ...] | None:
    """Every lock file that has to be this process's for one removal.

    The checkout's own two, and the one git takes for the branch its HEAD is
    on. That third one is what the first two do not cover: they are files in
    the tree's own git directory and they stop the commands that move a HEAD,
    while the branch under that HEAD lives in the store the whole clone
    shares and an `update-ref` on it is answerable to neither.

    The branch is named from the tree rather than from the candidate, because
    what has to be frozen is what this HEAD resolves through -- and the store
    is the clone's common directory, since a linked worktree keeps only
    `HEAD`, `refs/bisect/`, and `refs/worktree/` of its own.

    A HEAD on no branch needs no third lock and gets none. What it holds is
    the commit itself rather than a name resolving to one, and the two above
    are exactly what a `checkout`, a `reset`, or an `update-ref HEAD` has to
    take to move it -- so there is nothing under it left to freeze.

    `None` when a HEAD that IS on something could not be read, or when the
    store it lives in could not be named. Either way the removal stops: a pass
    that cannot say what the tree is standing on cannot hold it still, and a
    removal held still in part is one whose anchor promises more than it can
    keep.
    """
    checkout_locks = tuple(
        gitdir / lock_name for lock_name in _CHECKOUT_LOCKS
    )
    on_branch, branch = evidence._head_ref(worktree)
    if on_branch is ProbeAnswer.REFUTED:
        return checkout_locks
    common = evidence._common_git_dir(artifacts.spec.target_root)
    if on_branch is ProbeAnswer.UNREADABLE or common is None:
        log.warning(
            "issue=#%d keeping the checkout %s: the ref it is standing on "
            "could not be named, so it cannot be held still",
            artifacts.issue_number, worktree,
        )
        return None
    return (*checkout_locks, common / f"{_branch_ref(branch)}{_REF_LOCK}")


def _let_go(held: tuple[Path, ...]) -> None:
    """Give back the locks this took, whichever of them are still there.

    A removal that succeeded took the git directory and both locks with it,
    which is the ordinary way they go.
    """
    for lock in held:
        try:
            lock.unlink(missing_ok=True)
        except OSError as refused:
            log.warning(
                "the lock %s could not be given back: %s", lock, refused,
            )


def _removal_while_held(
    artifacts: IssueArtifacts,
    worktree: Path,
    proven_sha: str | None,
    gitdir: Path,
    pinned: int,
) -> SurfaceOutcome:
    """Pin what the checkout holds, take it down, and say what came with it.

    The hidden read is taken again here, last of everything and one process
    before the removal, because it is the only one of the readings behind this
    step that git does not make for itself. The locks stop a `commit` and a
    `checkout` in that tree; they stop nothing from WRITING in it, and a file
    the repository's rules cover is one `worktree remove` takes without a word
    -- so a reading from before the anchor would have this pass delete a
    secret that landed after it and report the surface cleaned.

    What is not retaken is what git refuses for itself. A tree that has gone
    dirty since is one the removal stops over, and a HEAD that has moved is
    what the anchor is read back against afterwards.
    """
    spec = artifacts.spec
    if not _anchor_taken(artifacts, worktree, proven_sha):
        return SurfaceOutcome.FAILED
    if not _ready_to_go(artifacts, worktree, proven_sha, gitdir, pinned):
        return _anchor_settled(
            artifacts, proven_sha, taken=SurfaceOutcome.FAILED,
        )
    removed = commands._git_hardened(
        "worktree", "remove", str(worktree), cwd=spec.target_root,
    )
    return _anchor_settled(
        artifacts, proven_sha,
        taken=_came_down(artifacts, worktree, removed),
    )


def _ready_to_go(
    artifacts: IssueArtifacts,
    worktree: Path,
    proven_sha: str | None,
    gitdir: Path,
    pinned: int,
) -> bool:
    """Everything this removal turns on, asked again with the locks held.

    The whole reading rather than the part git does not make for itself,
    because the locks go on after the first one and the window before them is
    one anybody can reach into. A checkout put on somebody else's branch there
    is one whose every later step reads as ours -- the branch this pass froze
    is the one it moved ONTO, the anchor pins whatever that branch stands on,
    and a tree that is clean on it is clean -- so the identity has to be
    established again where it cannot change afterwards, and that is here.

    What is asked is what the verdict was taken on: the path is this issue's
    own, the tree is a worktree of the configured clone standing on one of
    this issue's branches, its HEAD is on the commit that was cleared, and it
    is carrying and hiding nothing. Then the path is asked where it leads, and
    the registration is asked whether it is still the one this pass is holding
    -- neither of which is about the tree, and both of which decide what a
    command that resolves its own argument would take.
    """
    if not _still_ours(artifacts, worktree):
        return False
    if not _still_cleared(artifacts, worktree, proven_sha):
        return False
    return _registration_unchanged(artifacts, gitdir, pinned)


def _registration_unchanged(
    artifacts: IssueArtifacts, gitdir: Path, pinned: int,
) -> bool:
    """Whether the name the removal is aimed by still means what this holds.

    Taking the write bits off stops the command that rewrites that file in
    place. It stops nothing from replacing the NAME with a rename, which the
    directory above it permits and which leaves this pass holding an object
    the removal will never read.

    So the name is read once more and compared against what is held open: a
    file swapped underneath answers a different object, and the removal that
    would have been aimed by it does not run.
    """
    registration = gitdir / _REGISTRATION
    try:
        return _same_object(registration.lstat(), os.fstat(pinned))
    except OSError as read_error:
        log.warning(
            "issue=#%d keeping the checkout: %s could not be read back (%s)",
            artifacts.issue_number, registration, read_error,
        )
        return False


def _still_ours(artifacts: IssueArtifacts, worktree: Path) -> bool:
    """Whether the path about to be handed to git is still this checkout.

    The type first, as the scan reads it: anything at that path which is not a
    directory of its own is a name standing for a tree somewhere else, and
    handing one to a command that resolves what it is given is how a directory
    outside the tree this orchestrator owns comes down.

    Then where the path actually leads, because the type alone does not say.
    A checkout renamed away, its registration repaired to where it went, and a
    link left in its place is a path whose every reading before this answers
    about the tree at the far end -- and the removal would take that one.
    """
    if _checkout_present(worktree) is not ProbeAnswer.CONFIRMED:
        log.warning(
            "issue=#%d keeping %s: what is at that path is no longer a "
            "checkout this may take down", artifacts.issue_number, worktree,
        )
        return False
    return _same_place(artifacts, worktree)


def _same_place(artifacts: IssueArtifacts, worktree: Path) -> bool:
    """Whether the tree this path leads to is the tree this path is.

    Asked of git from inside the path, since what the removal turns on is
    where the path leads rather than how it is spelled -- and compared as
    filesystem objects rather than as spellings, because the two differ
    honestly all the time. An operator whose worktrees root sits under a link
    of their own has every checkout answering a resolved path that is not the
    one derived here, and it is the same directory; a link left in a
    checkout's place answers a directory somewhere else entirely.
    """
    located = commands._git_hardened(
        "rev-parse", "--show-toplevel", cwd=worktree,
    )
    named = (located.stdout or "").strip()
    if located.returncode != 0 or not named:
        log.warning(
            "issue=#%d keeping %s: it would not say which tree it leads to "
            "(%s)",
            artifacts.issue_number, worktree, (located.stderr or "").strip(),
        )
        return False
    if _one_directory(worktree, Path(named)):
        return True
    log.warning(
        "issue=#%d keeping %s: it leads to %s, which is not the tree this "
        "path is", artifacts.issue_number, worktree, named,
    )
    return False


def _one_directory(worktree: Path, located: Path) -> bool:
    """Whether two paths name one and the same directory on this host.

    The near one is read with `lstat` and the far one without: what is being
    told apart is a path that IS the tree from a path that merely leads to
    it, and following the first would answer the same for both.
    """
    try:
        return _same_object(worktree.lstat(), located.stat())
    except OSError as read_error:
        log.warning(
            "%s and %s could not be compared: %s",
            worktree, located, read_error,
        )
        return False


def _same_object(here: os.stat_result, there: os.stat_result) -> bool:
    """Whether two readings landed on one object, device and all."""
    return (here.st_dev, here.st_ino) == (there.st_dev, there.st_ino)


def _came_down(
    artifacts: IssueArtifacts,
    worktree: Path,
    removed: subprocess.CompletedProcess,
) -> SurfaceOutcome:
    """What became of the path this named, whatever the command answered.

    The last word on a step whose one argument is a path git resolves for
    itself, and the path is what it is read off rather than the exit status. A
    removal reporting success over a path still standing took something else
    down, and a surface reported cleaned over one would have the issue settled
    -- with whatever is still at that path never named by this host again.

    The other way round is the ordinary shape of two passes over one host: a
    command that refused over a path that is gone is this removal having
    happened without it, which is the success every other absence in this
    domain is. Reported apart from the deletion this pass made, so a caller
    counting what came down does not count one checkout twice.
    """
    if _checkout_present(worktree) is ProbeAnswer.REFUTED:
        return _nothing_left(artifacts, worktree, removed)
    if removed.returncode != 0:
        log.warning(
            "issue=#%d worktree remove of %s failed: %s",
            artifacts.issue_number, worktree, (removed.stderr or "").strip(),
        )
        return SurfaceOutcome.FAILED
    log.error(
        "issue=#%d worktree remove came back clean and %s is still there: "
        "what came down was not what this named",
        artifacts.issue_number, worktree,
    )
    return SurfaceOutcome.FAILED


def _nothing_left(
    artifacts: IssueArtifacts,
    worktree: Path,
    removed: subprocess.CompletedProcess,
) -> SurfaceOutcome:
    """What a path that is gone reports, told apart by who took it."""
    if removed.returncode == 0:
        return SurfaceOutcome.CLEANED
    log.info(
        "issue=#%d %s was already gone when this removal ran (%s)",
        artifacts.issue_number, worktree, (removed.stderr or "").strip(),
    )
    return SurfaceOutcome.ABSENT


def _anchor_taken(
    artifacts: IssueArtifacts, worktree: Path, proven_sha: str | None,
) -> bool:
    """Pin this checkout, once whatever an earlier pass pinned is settled.

    An anchor is created and never overwritten, and the pass that leaves one
    behind is not only the pass that meant to. A removal that raised, and a
    process that stopped between the note and the `worktree remove` it was
    for, both leave the note on disk with the checkout still standing -- and
    without this every later removal for that issue would be refused by a ref
    holding nothing anybody has to keep, forever.

    What the note pins is what tells that leftover from the thing the lease
    exists for. A commit this verdict has just cleared is one the
    classification proved outlives its artifact, so the ref is not the only
    name it has and nothing is lost by letting it go; anything else is work
    made in the window an earlier pass could not account for, and it goes on
    refusing.

    Cleared and taken again rather than reused, because the note lives in a
    ref store the agents this orchestrator runs can write. Reused, a note
    somebody planted at the cleared commit would BE the pinning the removal is
    measured against; taken again, what it is measured against is what git
    resolves from inside the checkout one process before the removal.
    """
    if not _spent_anchor_cleared(artifacts, proven_sha):
        return False
    if obligations._anchor_checkout(
        artifacts.spec, worktree, artifacts.issue_number,
    ):
        return True
    log.warning(
        "issue=#%d keeping the checkout %s: what it is standing on could "
        "not be pinned first", artifacts.issue_number, worktree,
    )
    return False


def _spent_anchor_cleared(
    artifacts: IssueArtifacts, proven_sha: str | None,
) -> bool:
    """Whether nothing an earlier pass pinned is standing in the way.

    Nothing at that name is the ordinary answer, and so is a read that
    established nothing: both go on to the write, which is leased against the
    ref existing and refuses for itself if there is one there after all. Only
    a note this pass can positively account for is taken away, and a note that
    would not go is one the removal does not run under -- the write after it
    would be refused by the same ref.
    """
    spec = artifacts.spec
    anchored = obligations._anchored_commit(spec, artifacts.issue_number)
    if not anchored:
        return True
    if anchored != proven_sha:
        log.error(
            "issue=#%d keeping the checkout: %s pins %r, which is not the %r "
            "this verdict cleared",
            artifacts.issue_number,
            obligations._anchor_ref(spec, artifacts.issue_number),
            anchored,
            proven_sha,
        )
        return False
    return _anchor_let_go(spec, artifacts.issue_number, anchored)


def _anchor_let_go(
    spec: config.RepoSpec, issue_number: int, expected: str,
) -> bool:
    """Take one issue's anchor away, and say so when it would not go.

    Answered rather than dropped at every call, because of what a note left
    standing costs the pass after this one: it is created and never
    overwritten, so one nobody could take away is one that has to be
    reconciled before anything else can be pinned for this issue.

    `expected` is what the caller read there and settled on, so a note moved
    since is one this refuses rather than takes: what an anchor is repointed
    at is a commit nobody established anything about, and the store it lives
    in is one an agent can write.
    """
    if obligations._discard_anchor(spec, issue_number, expected):
        return True
    log.warning(
        "issue=#%d %s would not go; the pass after this one settles it before "
        "it can pin anything of its own",
        issue_number, obligations._anchor_ref(spec, issue_number),
    )
    return False


def _anchor_settled(
    artifacts: IssueArtifacts,
    proven_sha: str | None,
    *,
    taken: SurfaceOutcome,
) -> SurfaceOutcome:
    """What the removal took, measured against what the verdict cleared.

    Equal is the ordinary answer, and the anchor goes: the commit it pinned is
    the one the classification proved survives its artifact, so nothing here
    is the only thing holding it.

    Anything else is work made before the locks went on, and it is kept under
    the anchor and reported at error. It also stands in the way of the
    removals after it, for as long as what it pins is a commit no verdict has
    cleared: what is there is a commit nothing else names, and an operator is
    the one who decides what becomes of it. The checkout is gone by then --
    that is what the anchor exists for -- but the commit is not, and the
    surface coming back failed is what has a later pass find the issue again.
    A commit nobody can name is reported the same way: an anchor that would
    not read back establishes nothing about what was taken.

    Asked on a removal that FAILED as squarely as on one that finished, which
    is what `taken` is for and nothing else. `worktree remove` is not one
    step: it deletes the tree, and then deletes the administrative directory
    beside it whatever the first half did -- there is no going back from a
    half-deleted checkout, so it does not try. A commit raced into the window
    is then held by an anchor whose reflog and HEAD have already gone, and a
    pass that let the note go because the command came back non-zero would
    take the last name that commit has. So the note is settled on what it
    pins, and only the answer this surface reports turns on what the removal
    left behind it.

    A note that would not go leaves the surface failed even when everything
    else finished. What is left behind is created and never overwritten, so it
    stands in front of every later removal for this issue -- and a teardown
    reporting itself settled over one would leave the note with nothing naming
    it.
    """
    spec = artifacts.spec
    anchored = obligations._anchored_commit(spec, artifacts.issue_number)
    if not anchored or anchored != proven_sha:
        log.error(
            "issue=#%d the checkout was on %r rather than the %r this verdict "
            "cleared; that commit is kept at %s",
            artifacts.issue_number,
            anchored or "a commit nobody could read back",
            proven_sha,
            obligations._anchor_ref(spec, artifacts.issue_number),
        )
        return SurfaceOutcome.FAILED
    if not _anchor_let_go(spec, artifacts.issue_number, anchored):
        return SurfaceOutcome.FAILED
    return taken


def _checkout_present(worktree: Path) -> ProbeAnswer:
    """Whether what is at this path is a checkout a removal may take.

    `REFUTED` is the path being gone, which is a removal that already
    happened. `UNREADABLE` is the host refusing to say -- a directory this
    process may not stat, a symlink loop -- and it is kept apart from the
    first because of what the first releases: an absence spent on a checkout
    nobody could see is a teardown reporting itself finished over a live tree.

    A path that is not a directory in its own right is `UNREADABLE` too, and
    the link is the one that matters. `worktree remove` resolves the path it
    is handed and deletes the REGISTERED tree it finds there, so a symlink
    left where this issue's checkout belongs, pointing at a worktree of this
    same clone somewhere else, has the removal succeed against a directory
    outside the tree this orchestrator owns -- and report it reclaimed. Every
    reading in front of it agrees, because every one of them follows the link
    and answers about the tree at the far end: it is a worktree of the
    configured clone, its HEAD is on this issue's branch, and it is carrying
    nothing loose. Only the mode of the path itself tells the two apart, which
    is why it is read here as the scan reads it.

    Read through `lstat` rather than `Path.exists`, which answers False for
    every `OSError` it meets and would hand exactly that reading over as an
    absence -- and which resolves what it is given, so a link would be
    answered for by whatever it points at.
    """
    try:
        node = worktree.lstat()
    except FileNotFoundError:
        return ProbeAnswer.REFUTED
    except OSError as read_error:
        log.warning(
            "the checkout %s could not be read: %s", worktree, read_error,
        )
        return ProbeAnswer.UNREADABLE
    if not S_ISDIR(node.st_mode):
        log.warning(
            "keeping %s: what is at this path is not a directory of its own, "
            "so removing it would take whatever it stands for", worktree,
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
    under, its HEAD is on the commit that was cleared, and it is holding
    nothing the removal would take with it.

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
    return _holding_nothing(artifacts, worktree)


def _holding_nothing(artifacts: IssueArtifacts, worktree: Path) -> bool:
    """Whether this tree PROVED there is nothing in it a removal would take.

    Two reads, because git draws the line between them and this boundary must
    not. Untracked and modified paths are what it calls dirty and what
    `worktree remove` refuses over without being asked; a path the
    repository's own ignore rules cover is neither, so a checkout holding
    nothing but those -- an `.env`, a key, a build root somebody is mid-way
    through -- answers clean to every other reading here and comes down with
    all of it inside.

    Stricter than git on purpose. What that command refuses is what a human
    running it interactively needs to be stopped over; what this refuses is
    what an unattended pass may destroy with nobody watching, and the two are
    not the same list.
    """
    if evidence._clean_worktree(worktree) is not ProbeAnswer.CONFIRMED:
        log.warning(
            "issue=#%d keeping %s: it has not proved it is carrying nothing "
            "loose", artifacts.issue_number, worktree,
        )
        return False
    if evidence._nothing_ignored(worktree) is not ProbeAnswer.CONFIRMED:
        log.warning(
            "issue=#%d keeping %s: it has not proved it is hiding nothing "
            "under its own ignore rules", artifacts.issue_number, worktree,
        )
        return False
    return True
