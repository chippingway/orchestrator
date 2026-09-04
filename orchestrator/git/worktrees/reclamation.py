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

Which branch to freeze is decided under those locks rather than in front of
them. An issue publishes under two names -- the slug-namespaced one and the
legacy flat one -- and both read as its own, so a checkout switched from one
to the other in the window before the locks would leave this pass holding the
ref it moved OFF while the ref it moved ONTO went on moving. HEAD is read once
`HEAD.lock` is this pass's, where it cannot change, and the third lock is
taken on what that read named -- and only where that name stands for itself.
Git reaches a loose ref by walking its path, so a room on the way replaced
with a link, or the ref itself replaced with one, files this issue's branch
where another name is: an `update-ref` on the far name then moves what this
checkout stands on while the lock sits at the near one. A ref this pass
cannot hold still by its own name is one it refuses rather than locks.

Every hold here is bound to the object it was taken on rather than to the name
it was taken at, because the names all sit in directories an agent can write.
A lock is given back only while the name still resolves to the file this pass
created; a lock a stopped pass left is taken away only while the name still
resolves to that exact leftover, so two passes meeting one leftover cannot
delete each other's live lock and both go on; and every lock is asked once
more, immediately before the removal, whether it is still the one this pass
took. Each is written whole under a name nothing can have planted -- created
for this pass alone rather than derived from the lock's own -- and then linked
to the name it is for, so what appears there appears complete and a write that
followed somebody's link could not have put this host's mark in their file.

The checkout itself is held open the same way, and for what no name can
answer afterwards. `worktree remove` resolves the path it is handed at the
moment it runs, and nothing this pass takes stops a rename in front of that:
a tree moved away and a copy of it left in its place is one every reading
about the PATH agrees with. So the descriptor opened before the readings is
what they are checked against and what the answer is read off -- a directory
nothing links to any more is one that came down, and a removal that took
anything else, or took nothing, is reported as the failure it is rather than
as this checkout's.

What the removal is aimed by is not the path it is handed either. That path
only selects a registration, and what comes down is the tree the registration
names -- so the registration is taken over rather than merely read: a file of
this pass's own, carrying exactly what the original said, is renamed over the
name and held open. A descriptor somebody opened before that lands on an inode
nothing is filed at any more, which is the one thing a mode cannot do; the
mode taken off what replaces it is what stops the `worktree repair` that would
open the name afresh; and the contents are read back through the held
descriptor before the removal, so a rewrite that got past both is refused
rather than aimed by.

Every name that is read here is read the same way, because two of them are
names an agent chooses what to put at: opened without following, refused
unless the descriptor is a regular file, and read to a bound with the byte
past that bound asked for as well. A fifo left at one of them would otherwise
block a pass that is holding git's own locks, and a pass that blocks holding
those never comes back to give them up; a file padded to exactly the bound
would otherwise read as the shorter thing it is not, and the take-over would
file that truncation at its name. Every write is finished for the same
reason: what a write took is what it says it took, and half a lock is one no
later pass can recognise.

What none of this reaches is a file the repository's own rules hide, arriving
in the window between the last reading and git's own. That reading is asked
last of everything for want of a way to make it later, and it is the one thing
here whose window a path-resolving command leaves open.

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
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from stat import S_IMODE, S_ISDIR, S_ISREG
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

# The suffix a staging file carries, which is what keeps it out of every ref
# listing while it is there: git skips a loose file whose name ends in this
# when it walks `refs/`, and the branch lock a removal takes is a name under
# exactly that room.
_STAGED_SUFFIX = ".lock"

# How much of one is read back. A lock this host wrote is a mark and a process
# id, so anything past this is not one -- and the read is bounded because the
# file sits where an agent can write.
_LOCK_LIMIT = 4096

# The file in a checkout's administrative directory that says where that
# checkout is. It is what `worktree remove` reads to decide what to delete and
# what `worktree repair` rewrites.
_REGISTRATION = "gitdir"

# What the copy this pass puts at that name is called while it is being
# written, before the rename that files it there. Named for the process that
# made it, so one left behind by a pass that stopped between the write and the
# rename is nobody else's to trip over and no note any reader here looks for.
_REPLACED_SUFFIX = ".orchestrator-reclaim."

# How that copy is created: for this pass alone, and readable as well as
# writable, since the contents are read back through this same descriptor
# immediately before the removal.
_REPLACING = os.O_CREAT | os.O_EXCL | os.O_RDWR

_WRITABLE = 0o222

# What a registration always carries when git wrote it, and what one is given
# back regardless: a mode without it is this host's own hold, left by a pass
# that did not come back to release it.
_OWNER_WRITE = 0o200

# How the checkout itself is opened and held for the length of a removal: as
# a directory in its own right, without following and without waiting. What
# the descriptor is for is what no path can answer afterwards -- whether the
# tree this pass validated is the tree that came down.
_CHECKOUT_HANDLE = (
    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
)

# What `st_nlink` reads as once nothing on this host names an object any more,
# which for a directory is the `rmdir` that ended it.
_UNLINKED = 0

# How every name an agent can choose what to put at is opened: read-only,
# refusing to follow, and refusing to wait. A link at the name fails the open
# outright rather than handing this pass somebody else's file, and a fifo
# answers immediately rather than blocking a pass that is holding git's locks.
_UNFOLLOWED = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK

# How much of a registration is read. One is a path and a newline, so anything
# past this is not one -- and the read is bounded because the file is one an
# agent can write.
_REGISTRATION_LIMIT = 4096


@dataclass(frozen=True)
class _HeldLock:
    """One lock file this pass created, and the line the create wrote in it.

    The line rather than the name alone, because everything done to a lock
    afterwards -- giving it back, and asking whether it is still ours -- has
    to be about the file this pass took and not about whatever is at that name
    by then.

    The line rather than the object, too. A lock lives for the length of a
    removal and this pass does not hold it open, so a name unlinked and
    created again may come back carrying the very inode the first one had --
    and a comparison of device and inode would call that the same file. What
    this host writes into every lock it takes names the process that took it,
    which no other pass can be carrying at the same moment.
    """

    named: Path
    taken: str


@dataclass(frozen=True)
class _Registration:
    """The file one removal is aimed by, as this pass took it over.

    `says` is what it names, which is the whole of what decides where the
    destruction lands, so it is carried rather than re-derived: what the
    reading before the removal compares against is the exact text this pass
    established was this checkout's own.
    """

    named: Path
    pinned: int
    was: int
    says: str


@dataclass(frozen=True)
class _Holds:
    """Everything one removal runs under, in the shape it is checked in."""

    checkout: int
    locks: tuple[_HeldLock, ...]
    registration: _Registration


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
    if present is ProbeAnswer.UNREADABLE:
        return SurfaceOutcome.FAILED
    if not _still_cleared(artifacts, worktree, proven_sha):
        return SurfaceOutcome.FAILED
    if not _holding_nothing(artifacts, worktree):
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
        held = _everything_held(artifacts, worktree, gitdir, holding)
        if held is None:
            return SurfaceOutcome.FAILED
        return _removal_while_held(artifacts, worktree, proven_sha, held)


def _everything_held(
    artifacts: IssueArtifacts,
    worktree: Path,
    gitdir: Path,
    holding: contextlib.ExitStack,
) -> _Holds | None:
    """Take every hold one removal runs under, or come back with none.

    Git's own locks for the tree and the branch under its HEAD, and then the
    registration the removal will be aimed by. Each is given back through the
    stack the caller opened, so a hold taken is a hold released however this
    ends -- and what is handed back is each of them as the object it was taken
    on, since the readings before the removal have to be able to ask whether
    the names still mean them.
    """
    checkout = _checkout_handle(artifacts, worktree)
    if checkout is None:
        return None
    holding.callback(os.close, checkout)
    held = _held_still(artifacts, worktree, gitdir)
    if not held:
        return None
    holding.callback(_let_go, held)
    registration = _registration_held(artifacts, gitdir, worktree)
    if registration is None:
        return None
    holding.callback(_thawed, registration)
    return _Holds(checkout, held, registration)


def _checkout_handle(
    artifacts: IssueArtifacts, worktree: Path,
) -> int | None:
    """Open the checkout itself, to be held until the removal is over.

    The one hold here that is not about stopping anything. `worktree remove`
    resolves the path it is handed at the moment it runs, and nothing this
    pass can take stops a rename in front of that -- so what the descriptor is
    for is afterwards: a directory nothing links to any more is one that was
    removed, and a path that is gone says only that something took the name.
    Held from before the readings, it is also what those readings are checked
    against, so the tree they clear is the tree the answer is read off.

    Opened as a directory in its own right, without following and without
    waiting, for the reason every name here is: a link where the checkout
    belongs is refused rather than followed to whatever it stands for.
    """
    try:
        return os.open(worktree, _CHECKOUT_HANDLE)
    except OSError as refused:
        log.warning(
            "issue=#%d keeping the checkout %s: it would not open as a "
            "directory of its own (%s)",
            artifacts.issue_number, worktree, refused,
        )
        return None


def _registration_held(
    artifacts: IssueArtifacts, gitdir: Path, worktree: Path,
) -> _Registration | None:
    """Take hold of the file this removal will be aimed by, or refuse.

    What `worktree remove` deletes is not the path it is handed. That path
    only selects a registration, and what comes down is the path the
    registration names -- so the one thing deciding where the destruction
    lands is a file in the administrative directory, and `worktree repair` is
    a single command that rewrites it.

    Read first, and then taken over. Reading alone would leave the pass
    holding a descriptor onto a file anybody who already opened it can rewrite
    at any moment -- the mode says nothing to a descriptor that exists -- so
    what ends up filed at the name is a file of this pass's own carrying
    exactly what the original said, and every writer who came before is left
    holding an inode nothing is filed at.

    The original is held open from the reading that validates it to the rename
    that displaces it, and that is what makes the take-over safe to do at all.
    What is filed at the name is a copy of what the original SAID, so a
    `worktree move` landing between the two would have this pass write a path
    nothing is at over the path git had just recorded -- destroying the
    registration of a checkout it then refuses to touch. Held open, the
    original can be asked one last time whether it is still the file that was
    read and still says what it said, and it is asked immediately before the
    rename with nothing in between.

    `None` for anything that is not this checkout's own registration, and for
    every reading that could not be taken: a removal aimed by a file this pass
    cannot account for is aimed at nothing in particular.
    """
    named = gitdir / _REGISTRATION
    opened = _registration_opened(artifacts, named)
    if opened is None:
        return None
    with contextlib.ExitStack() as reading:
        reading.callback(os.close, opened)
        return _registration_taken(artifacts, named, worktree, opened)


def _registration_opened(artifacts: IssueArtifacts, named: Path) -> int | None:
    """Open the file a removal is aimed by, without following or waiting.

    Without following, which is the first of the two things this is for. A
    link left at that name would have every reading here answer about somebody
    else's file and every write land on it, so a link is not read around -- it
    is refused, and the removal with it.

    Without waiting, which is the second. A fifo at the name is something an
    agent can leave there, and an open of one blocks until somebody writes --
    with this pass holding git's own locks for the checkout and the target
    root while it waits.
    """
    try:
        return os.open(named, _UNFOLLOWED)
    except OSError as refused:
        log.warning(
            "issue=#%d keeping the checkout: %s would not open as a file of "
            "its own (%s)", artifacts.issue_number, named, refused,
        )
        return None


def _registration_taken(
    artifacts: IssueArtifacts, named: Path, worktree: Path, opened: int,
) -> _Registration | None:
    """Validate what is filed at that name and take it over, still holding it.

    Both halves run against the one descriptor the open established, so what
    is taken over is the file that was validated rather than whatever the name
    means by the time the rename runs.
    """
    read = _registration_checked(artifacts, worktree, opened)
    if read is None:
        return None
    return _registration_replaced(artifacts, named, opened, read)


def _registration_checked(
    artifacts: IssueArtifacts, worktree: Path, opened: int,
) -> tuple[int, str] | None:
    """The mode and contents of a registration that aims at this checkout.

    The descriptor is asked what it is before it is asked what it says, since
    what the open refused to wait for is the read: a fifo answers the open at
    once and then blocks whoever reads it, and anything that is not a regular
    file is refused rather than read.

    A registration names this checkout's own `.git`, which is what says the
    removal about to run is aimed here rather than at a tree somebody repaired
    it onto. Compared as filesystem objects for the reason every path
    comparison here is: the spellings differ honestly under a worktrees root
    that sits below a link of its own.
    """
    try:
        told = _registration_told(opened)
    except (OSError, ValueError) as unread:
        log.warning(
            "issue=#%d keeping the checkout %s: its registration could not be "
            "read (%s)", artifacts.issue_number, worktree, unread,
        )
        return None
    if told is not None and _aims_here(worktree, told[1]):
        return told
    log.warning(
        "issue=#%d keeping the checkout %s: what is registered for it is not "
        "a file naming this tree", artifacts.issue_number, worktree,
    )
    return None


def _registration_told(opened: int) -> tuple[int, str] | None:
    """The mode and the contents of a descriptor, if it is a regular file."""
    held = os.fstat(opened)
    if not S_ISREG(held.st_mode):
        return None
    return S_IMODE(held.st_mode), _registration_read(opened)


def _registration_read(pinned: int) -> str:
    """What the registration this pass holds says, from its first byte.

    Read at an offset rather than at wherever the descriptor happens to be,
    so the reading before the removal is the same reading as the one that
    established what the file said in the first place.

    One byte past the bound is asked for, and anything that answers it is
    refused rather than cut short. A registration is one path and a newline,
    so a longer one is not a registration at all -- and reading only as far as
    the bound would have a file padded to exactly the right prefix pass every
    comparison here while the take-over filed the truncation at its name.
    """
    read = os.pread(pinned, _REGISTRATION_LIMIT + 1, 0)
    if len(read) > _REGISTRATION_LIMIT:
        raise ValueError(
            f"a registration is not {_REGISTRATION_LIMIT} bytes or more",
        )
    return read.decode()


def _written_whole(writing: int, written: bytes) -> None:
    """Write the whole of one buffer, however little a call takes at a time.

    A write is allowed to take less than it was given, and a caller reading
    its answer as "done" would file half a registration -- or a lock carrying
    a mark no later pass can recognise, which is one that refuses its issue
    for good. What was left is offered again until the buffer is out, and a
    write taking nothing at all is the failure it is.
    """
    put = 0
    whole = len(written)
    while put < whole:
        wrote = os.write(writing, written[put:])
        if not wrote:
            raise OSError(f"a write of {whole} bytes would not finish")
        put += wrote


def _registration_replaced(
    artifacts: IssueArtifacts,
    named: Path,
    opened: int,
    read: tuple[int, str],
) -> _Registration | None:
    """Put a file of this pass's own at that name, and hold that one.

    The rename is what makes the hold real. Taking the write bits off what was
    already there stops a command that opens the name afresh -- `worktree
    repair` is one, and it is the one that would aim the removal elsewhere --
    and says nothing at all to a descriptor somebody opened earlier and kept.
    A file created here, written with exactly what the original said, and
    renamed over the name leaves every one of those descriptors pointing at an
    inode no name resolves to any more.

    Held by a descriptor rather than by a name from then on. What the write
    bits come off is the object created here and never whatever the name means
    by then, and what they go back onto is that same object however the name
    has been rearranged since.

    A pass that stops between the write and the rename leaves its copy under a
    name of its own beside the registration. Nothing reads that name, and the
    next pass writes another rather than trusting one it finds.
    """
    was, says = read
    staged = named.with_name(f"{named.name}{_REPLACED_SUFFIX}{os.getpid()}")
    pinned = _registration_staged(artifacts, staged, was, says)
    if pinned is None:
        return None
    if not _registration_filed(artifacts, staged, named, opened, says):
        os.close(pinned)
        _registration_dropped(staged)
        return None
    if _mode_taken_off(artifacts, pinned, was) is None:
        os.close(pinned)
        return None
    return _Registration(named, pinned, was, says)


def _registration_staged(
    artifacts: IssueArtifacts, staged: Path, was: int, says: str,
) -> int | None:
    """Write this pass's copy under a name of its own, and hold it open."""
    try:
        pinned = os.open(staged, _REPLACING, was)
    except OSError as refused:
        log.warning(
            "issue=#%d keeping the checkout: its registration could not be "
            "taken over (%s)", artifacts.issue_number, refused,
        )
        return None
    try:
        _written_whole(pinned, says.encode())
    except OSError as refused:
        log.warning(
            "issue=#%d keeping the checkout: its registration could not be "
            "written back (%s)", artifacts.issue_number, refused,
        )
        os.close(pinned)
        _registration_dropped(staged)
        return None
    return pinned


def _registration_filed(
    artifacts: IssueArtifacts,
    staged: Path,
    named: Path,
    opened: int,
    says: str,
) -> bool:
    """File this pass's copy at the name, while the name still means the same.

    The last thing asked before a rename that cannot be undone: the name still
    resolves to the object this pass validated, and that object still says
    what it said. A `worktree move` rewrites this file in place, so the second
    question is the one that catches it -- and what the rename would otherwise
    file is a path git has just stopped recording, leaving a checkout that
    survived registered where it no longer is.

    The asking and the rename are as close together as two calls can be. What
    a name-based protocol cannot offer is doing them as one, and the writer
    that would have to land between them is one already racing git's own
    non-atomic rewrite of the same file.
    """
    try:
        still = _registration_still(named, opened, says)
    except (OSError, ValueError) as unread:
        log.warning(
            "issue=#%d keeping the checkout: %s could not be read back before "
            "the take-over (%s)", artifacts.issue_number, named, unread,
        )
        return False
    if not still:
        log.warning(
            "issue=#%d keeping the checkout: %s stopped being the "
            "registration this pass read", artifacts.issue_number, named,
        )
        return False
    try:
        os.replace(staged, named)
    except OSError as refused:
        log.warning(
            "issue=#%d keeping the checkout: its registration could not be "
            "taken over (%s)", artifacts.issue_number, refused,
        )
        return False
    return True


def _registration_still(named: Path, opened: int, says: str) -> bool:
    """Whether that name still holds the file that was read, saying the same."""
    return _same_object(
        named.lstat(), os.fstat(opened),
    ) and _registration_read(opened) == says


def _registration_dropped(staged: Path) -> None:
    """Take this pass's copy away, wherever the take-over ended."""
    with contextlib.suppress(OSError):
        staged.unlink()


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


def _thawed(registration: _Registration) -> None:
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
        os.fchmod(registration.pinned, registration.was | _OWNER_WRITE)
    except OSError as refused:
        log.warning("a registration's mode could not go back: %s", refused)
    finally:
        os.close(registration.pinned)


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
) -> tuple[_HeldLock, ...]:
    """Take git's own locks for one checkout, or come back with none.

    The checkout's own two first, and the branch its HEAD is on decided only
    once they are this pass's. A HEAD is read to know which ref to freeze, and
    a HEAD read before `HEAD.lock` exists is one that can change afterwards --
    an issue publishes under two names and both read as its own, so a checkout
    switched between them in that window would leave this pass freezing the
    ref it moved off while the ref it moved onto stayed free to move.

    Only what was actually taken is reported, so what is given back afterwards
    is only ever this process's own.
    """
    taken = _all_taken(artifacts, _own_locks(gitdir))
    if taken is None:
        return ()
    under = _branch_lock(artifacts, worktree)
    if under is None:
        _let_go(taken)
        return ()
    beneath = _all_taken(artifacts, under)
    if beneath is None:
        _let_go(taken)
        return ()
    return taken + beneath


def _all_taken(
    artifacts: IssueArtifacts, wanted: tuple[Path, ...],
) -> tuple[_HeldLock, ...] | None:
    """Take every one of these locks, or give back the ones that were taken."""
    taken: list[_HeldLock] = []
    for lock in wanted:
        held = _taken_once(artifacts, lock)
        if held is None:
            _let_go(tuple(taken))
            return None
        taken.append(held)
    return tuple(taken)


def _own_locks(gitdir: Path) -> tuple[Path, ...]:
    """The two lock files a checkout keeps in its own git directory."""
    return tuple(gitdir / lock_name for lock_name in _CHECKOUT_LOCKS)


def _branch_lock(
    artifacts: IssueArtifacts, worktree: Path,
) -> tuple[Path, ...] | None:
    """The lock git takes for the branch this checkout's HEAD is on.

    What the checkout's own two do not cover: they are files in the tree's own
    git directory and they stop the commands that move a HEAD, while the
    branch under that HEAD lives in the store the whole clone shares and an
    `update-ref` on it is answerable to neither.

    The branch is named from the tree rather than from the candidate, because
    what has to be frozen is what this HEAD resolves through -- and the store
    is the clone's common directory, since a linked worktree keeps only
    `HEAD`, `refs/bisect/`, and `refs/worktree/` of its own.

    A HEAD on no branch needs no third lock and gets none. What it holds is
    the commit itself rather than a name resolving to one, and the two already
    held are exactly what a `checkout`, a `reset`, or an `update-ref HEAD` has
    to take to move it -- so there is nothing under it left to freeze.

    `None` when a HEAD that IS on something could not be read, or when the
    store it lives in could not be named. Either way the removal stops: a pass
    that cannot say what the tree is standing on cannot hold it still, and a
    removal held still in part is one whose anchor promises more than it can
    keep.
    """
    on_branch, branch = evidence._head_ref(worktree)
    if on_branch is ProbeAnswer.REFUTED:
        return ()
    common = evidence._common_git_dir(artifacts.spec.target_root)
    if on_branch is ProbeAnswer.UNREADABLE or common is None:
        log.warning(
            "issue=#%d keeping the checkout %s: the ref it is standing on "
            "could not be named, so it cannot be held still",
            artifacts.issue_number, worktree,
        )
        return None
    ref = _branch_ref(branch)
    if not obligations._direct_note(artifacts.spec, ref):
        log.warning(
            "issue=#%d keeping the checkout %s: %s stands for another name "
            "rather than for itself, so a lock at it holds nothing",
            artifacts.issue_number, worktree, ref,
        )
        return None
    return (common / f"{ref}{_REF_LOCK}",)


def _taken_once(artifacts: IssueArtifacts, lock: Path) -> _HeldLock | None:
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

    Taking one away is bound to the exact leftover that was read, never to the
    name it was read at: two passes meeting one leftover at the same moment
    would otherwise each delete what the other had just created and both go
    on, which is the one outcome a lock exists to prevent.
    """
    created = _lock_created(lock)
    if created is not None:
        return created
    was = _left_behind(lock)
    if was is None:
        log.warning(
            "issue=#%d keeping the checkout: %s is already held",
            artifacts.issue_number, lock,
        )
        return None
    log.warning(
        "issue=#%d %s was left behind by a pass that did not come back, and "
        "is taken again", artifacts.issue_number, lock,
    )
    if not _stale_let_go(lock, was):
        return None
    return _lock_created(lock)


def _lock_created(lock: Path) -> _HeldLock | None:
    """File one lock for this process alone, whole, marked as this host's.

    The mark is what a later pass reads to tell this host's own leftover from
    a lock some git command is holding right now: git writes its own content
    into each of these -- an index, a ref line, an object id -- and never
    this.

    Written under a name of this pass's own and then LINKED to the lock's, so
    what appears at that name appears complete. Creating the lock and marking
    it afterwards leaves a window where the name exists carrying nothing, and
    a lock carrying nothing is one no later pass can recognise as this host's:
    it reads as a command's, is never taken again, and refuses every removal
    for that issue from then on. A write that fails and a process that stops
    are the same event through that window, and neither can reach it here --
    the link is the whole of the taking, and it is refused outright when
    something is already at the name.

    Room is made first, because a ref that has been packed away leaves none:
    the loose file under `refs/heads/` is what `pack-refs` removes, and the
    directories above it go with it. Git makes the same room when it takes the
    same lock, and an empty one it finds instead is one it prunes. A room that
    could not be made is not answered here -- the write that follows fails on
    its own and says so.

    What comes back is the line the create wrote, so a lock this pass took is
    one it can recognise again whatever has since been done to the name.
    """
    with contextlib.suppress(OSError):
        lock.parent.mkdir(parents=True, exist_ok=True)
    marked = f"{_LOCK_MARK} {os.getpid()}\n"
    try:
        staged = _lock_staged(lock, marked)
    except OSError as refused:
        log.warning("the lock %s could not be written: %s", lock, refused)
        return None
    with contextlib.ExitStack() as filing:
        filing.callback(_lock_dropped, staged)
        return _lock_filed(lock, staged, marked)


def _lock_staged(lock: Path, marked: str) -> Path:
    """Write one lock's whole content under a name nothing can have planted.

    Created rather than opened, and at a name this pass is handed rather than
    one it derives. A staging name anybody can predict is one an agent can put
    a link at, and a write that followed it would put this host's mark into
    somebody else's file -- and then hard-link that file in as the lock every
    later pass reads. A name that does not exist until this call makes it has
    nothing to follow and nothing to wait on.

    The suffix is what keeps it out of every ref listing while it is there:
    git skips a loose file whose name ends in it, and one of the three locks a
    removal takes lives under `refs/heads/`.
    """
    writing, named = tempfile.mkstemp(
        prefix=f"{lock.name}.", suffix=_STAGED_SUFFIX, dir=lock.parent,
    )
    staged = Path(named)
    try:
        with contextlib.ExitStack() as taking:
            taking.callback(os.close, writing)
            _written_whole(writing, marked.encode())
    except OSError:
        _lock_dropped(staged)
        raise
    return staged


def _lock_filed(lock: Path, staged: Path, marked: str) -> _HeldLock | None:
    """File the staged lock at the name it is for, or leave that name alone.

    `None` is the name already being taken, which is what the link answers
    with rather than an exception this reads as a failure to write: a lock
    somebody else is holding is the ordinary answer, and the caller tells it
    from a leftover of this host's by reading what is there.
    """
    try:
        os.link(staged, lock)
    except OSError:
        return None
    return _HeldLock(lock, marked)


def _lock_dropped(staged: Path) -> None:
    """Take the staging file away, wherever the taking ended."""
    with contextlib.suppress(OSError):
        staged.unlink()


def _left_behind(lock: Path) -> str | None:
    """What a lock a stopped pass of this host's left there says, if it is one.

    Two things have to hold, and neither is enough on its own. The mark says
    the file is one this orchestrator wrote rather than one git is holding,
    and the process it names has to be gone -- a sibling pass on the same
    clone being exactly what a lock is for.

    Everything else is left alone: a file this cannot read, one that is not a
    regular file at all, a mark it does not know, a process still running, and
    one this host may not signal, which is somebody else's however it came by
    that number.

    The line is what comes back rather than a yes, because the deletion this
    answer allows has to be about that exact leftover and not about the name.
    """
    written = _lock_says(lock)
    if written is None:
        return None
    named = _lock_names(written)
    if named is None or _process_alive(named):
        return None
    return written


def _lock_says(lock: Path) -> str | None:
    """What one lock file says, or nothing when it will not answer as one.

    Opened the way every agent-writable name here is opened: without
    following, without waiting, and asked what it is before it is asked what
    it says. A fifo at a lock's name would otherwise block a pass that is
    already holding git's locks for this checkout, and a pass that blocks
    there never comes back to give them up.
    """
    try:
        opened = os.open(lock, _UNFOLLOWED)
    except OSError:
        return None
    try:
        return _lock_told(opened)
    except (OSError, ValueError):
        return None
    finally:
        os.close(opened)


def _lock_told(opened: int) -> str | None:
    """What a descriptor says, if what it is open on is a lock at all.

    A regular file, and one no longer than a lock this host writes: a mark and
    a process id is the whole of one, so a file that answers past the bound is
    something else and is refused rather than read up to it.
    """
    if not S_ISREG(os.fstat(opened).st_mode):
        return None
    read = os.read(opened, _LOCK_LIMIT + 1)
    return None if len(read) > _LOCK_LIMIT else read.decode()


def _lock_names(written: str) -> int | None:
    """The process one of this host's own locks names, if it is one of them."""
    marked, _sep, named = written.partition(" ")
    if marked != _LOCK_MARK or not named.strip().isdigit():
        return None
    return int(named) or None


def _lock_still(lock: Path, taken: str) -> bool:
    """Whether the file at this name is still the one that said this."""
    return _lock_says(lock) == taken


def _process_alive(named: int) -> bool:
    """Whether one process id still names something running on this host."""
    try:
        os.kill(named, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _stale_let_go(lock: Path, was: str) -> bool:
    """Take away the exact leftover that was read, and nothing else.

    The name is read once more and compared against the line the staleness was
    established on, because between the two another pass may have taken the
    same leftover away and created a live lock of its own at that name.
    Deleting by name alone is how both of them end up holding a lock neither
    of them has.
    """
    if not _lock_still(lock, was):
        log.warning(
            "%s is no longer the lock that was left behind, so it stays", lock,
        )
        return False
    try:
        lock.unlink()
    except OSError as refused:
        log.warning("the lock %s could not be taken again: %s", lock, refused)
        return False
    return True


def _let_go(held: tuple[_HeldLock, ...]) -> None:
    """Give back the locks this took, whichever of them are still ours.

    Compared before it is deleted, for the same reason it was taken on an
    object rather than on a name: a lock removed from under this pass and
    recreated by another is one this must not take away on its way out.

    A removal that succeeded took the git directory and both locks with it,
    which is the ordinary way they go.
    """
    for lock in held:
        if not _lock_still(lock.named, lock.taken):
            continue
        try:
            lock.named.unlink(missing_ok=True)
        except OSError as refused:
            log.warning(
                "the lock %s could not be given back: %s",
                lock.named, refused,
            )


def _locks_unchanged(
    artifacts: IssueArtifacts, held: tuple[_HeldLock, ...],
) -> bool:
    """Whether every lock this pass took is still the one it took.

    Asked immediately before the removal, because a lock file is a name in a
    directory an agent can write and nothing about creating one stops somebody
    removing it afterwards. A name that no longer resolves to the object this
    pass created is a checkout something else is free to be committing in, and
    the whole of what the removal is measured against rests on it.
    """
    for lock in held:
        if not _lock_still(lock.named, lock.taken):
            log.warning(
                "issue=#%d keeping the checkout: %s is no longer the lock "
                "this pass took", artifacts.issue_number, lock.named,
            )
            return False
    return True


def _removal_while_held(
    artifacts: IssueArtifacts,
    worktree: Path,
    proven_sha: str | None,
    held: _Holds,
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
    if not _ready_to_go(artifacts, worktree, proven_sha, held):
        return _anchor_settled(
            artifacts, proven_sha, taken=SurfaceOutcome.FAILED,
        )
    removed = commands._git_hardened(
        "worktree", "remove", str(worktree), cwd=spec.target_root,
    )
    return _anchor_settled(
        artifacts, proven_sha,
        taken=_came_down(artifacts, worktree, removed, held.checkout),
    )


def _ready_to_go(
    artifacts: IssueArtifacts,
    worktree: Path,
    proven_sha: str | None,
    held: _Holds,
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
    is standing on the commit that was cleared. Then the holds themselves are
    asked whether they are still holding -- the locks, and the registration
    this removal is aimed by -- neither of which is about the tree, and both
    of which decide what a command that resolves its own argument would take.

    What the tree is carrying and hiding comes last of everything, with the
    removal the next thing after it. It is the one reading git does not make
    for itself -- an ignored file is what `worktree remove` takes without a
    word -- so it is asked where the window in front of the command is as
    short as this pass can make it.
    """
    if not _still_ours(artifacts, worktree, held.checkout):
        return False
    if not _still_cleared(artifacts, worktree, proven_sha):
        return False
    if not _locks_unchanged(artifacts, held.locks):
        return False
    if not _registration_unchanged(artifacts, held.registration):
        return False
    return _holding_nothing(artifacts, worktree)


def _registration_unchanged(
    artifacts: IssueArtifacts, registration: _Registration,
) -> bool:
    """Whether the file the removal is aimed by still says what it said.

    Two questions, because two different things can happen to it. The name can
    be pointed at another file, which a rename through the writable directory
    above does and which leaves this pass holding an object the removal will
    never read; and the file itself can be rewritten, which anybody who put
    the write bits back can do and which changes where the destruction lands
    without changing what is filed at the name.

    So the name is read once more and compared against what is held open, and
    then the held object is read back and compared against what it said when
    this pass established it was this checkout's own. Either one differing and
    the removal does not run.
    """
    try:
        filed, says = _registration_now(registration)
    except (OSError, ValueError) as read_error:
        log.warning(
            "issue=#%d keeping the checkout: %s could not be read back (%s)",
            artifacts.issue_number, registration.named, read_error,
        )
        return False
    if not filed:
        log.warning(
            "issue=#%d keeping the checkout: %s is no longer the file this "
            "pass is holding", artifacts.issue_number, registration.named,
        )
        return False
    if says == registration.says:
        return True
    log.warning(
        "issue=#%d keeping the checkout: its registration now names %r",
        artifacts.issue_number, says.strip(),
    )
    return False


def _registration_now(registration: _Registration) -> tuple[bool, str]:
    """Whether the name still holds what is pinned, and what it says now."""
    return (
        _same_object(
            registration.named.lstat(), os.fstat(registration.pinned),
        ),
        _registration_read(registration.pinned),
    )


def _still_ours(
    artifacts: IssueArtifacts, worktree: Path, checkout: int,
) -> bool:
    """Whether the path about to be handed to git is still this checkout.

    The type first, as the scan reads it: anything at that path which is not a
    directory of its own is a name standing for a tree somewhere else, and
    handing one to a command that resolves what it is given is how a directory
    outside the tree this orchestrator owns comes down.

    Then whether the name still leads to the directory this pass has held open
    since before the readings. That is what binds the whole of the rest to one
    object: every clearance below is about the tree at this path, and the
    answer read off the removal afterwards is about the tree behind that
    descriptor, so the two have to be the same tree or neither means anything.

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
    if not _checkout_held(artifacts, worktree, checkout):
        return False
    return _same_place(artifacts, worktree)


def _checkout_held(
    artifacts: IssueArtifacts, worktree: Path, checkout: int,
) -> bool:
    """Whether that path still leads to the tree this pass is holding open."""
    try:
        held = _same_object(worktree.lstat(), os.fstat(checkout))
    except OSError as read_error:
        log.warning(
            "issue=#%d keeping %s: it could not be compared against the "
            "checkout this pass holds open (%s)",
            artifacts.issue_number, worktree, read_error,
        )
        return False
    if held:
        return True
    log.warning(
        "issue=#%d keeping %s: it is no longer the checkout this pass opened",
        artifacts.issue_number, worktree,
    )
    return False


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
    checkout: int,
) -> SurfaceOutcome:
    """What became of the tree this pass validated, whatever the command said.

    Read off the directory itself rather than off the path or the exit status,
    because both of those answer about a NAME. `worktree remove` resolves the
    path it is handed at the moment it runs, and nothing this pass holds stops
    a rename in front of that: a tree moved away and a fresh directory left in
    its place has the command act on the replacement, and a path that is gone
    afterwards says only that something took the name. The descriptor held
    open since the readings answers about the tree -- a directory nothing
    links to any more is one that was removed -- so a removal that took
    something else, or took nothing, cannot be reported as one that took this.

    Then which of the two ways it went, told apart by who did it. The command
    reporting success is this pass's own deletion; one that refused over a
    checkout gone all the same is this removal having happened without it,
    which is the success every other absence in this domain is. Reported apart
    so a caller counting what came down does not count one checkout twice.
    """
    gone = _checkout_gone(checkout)
    if gone is None:
        log.error(
            "issue=#%d %s could not be read back after the removal, so what "
            "came down is not established",
            artifacts.issue_number, worktree,
        )
        return SurfaceOutcome.FAILED
    if gone:
        return _nothing_left(artifacts, worktree, removed)
    if removed.returncode != 0:
        log.warning(
            "issue=#%d worktree remove of %s failed: %s",
            artifacts.issue_number, worktree, (removed.stderr or "").strip(),
        )
        return SurfaceOutcome.FAILED
    log.error(
        "issue=#%d worktree remove came back clean and the checkout %s named "
        "is still standing: what came down was not what this named",
        artifacts.issue_number, worktree,
    )
    return SurfaceOutcome.FAILED


def _checkout_gone(checkout: int) -> bool | None:
    """Whether nothing on this host links to the tree this pass held open."""
    try:
        return os.fstat(checkout).st_nlink == _UNLINKED
    except OSError as read_error:
        log.warning(
            "the checkout this pass held open could not be read back: %s",
            read_error,
        )
        return None


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
    under, and its HEAD is on the commit that was cleared. What it is carrying
    and hiding is asked apart from these, because it is asked at a different
    moment: these settle whose tree it is, and that one has to be the last
    word before the removal.

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
    return True


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
