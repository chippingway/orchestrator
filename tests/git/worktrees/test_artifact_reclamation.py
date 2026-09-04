# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a checkout teardown takes down, what it refuses, and what it pins.

Driven over a real clone and real checkouts, because every claim here is about
what git was left holding: a tree that is gone, a tree that is not, a note
standing over a commit nothing else names. The verdicts come from the
classifier itself, so the proof each case spends is the one production spends.

The failures are made rather than mocked wherever the host can make them -- a
locked worktree, a branch committed onto after the proof, a registration
replaced underneath -- because what is under test is the refusal, and a
refusal driven by a stub of the reading it refuses on proves only that the
stub was consulted.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from stat import S_IMODE
from unittest.mock import patch

from orchestrator.git import commands
from orchestrator.git.worktrees import evidence, obligations, reclamation
from orchestrator.git.worktrees.models import (
    ArtifactVerdict,
    BranchTip,
    ProbeAnswer,
    ProvenTip,
    SurfaceOutcome,
)
from tests.git.worktrees.artifact_test_support import (
    WIDGET_SLUG,
    _legacy_branch,
    _namespaced_branch,
)
from tests.git.worktrees.candidate_host_test_support import (
    _branch_at,
    _index_path,
    _track_file,
)
from tests.git.worktrees.eligibility_test_support import (
    ISSUE_NUMBER,
    _candidate,
    _github,
    _terminal_issue,
)
from tests.git.worktrees.reclamation_test_support import (
    GIT_FILE,
    OTHER_ISSUE_NUMBER,
    _checkout_surface,
    _dirty,
    _left_aside,
    _ran_git,
    _ReclaimTestCase,
    _removal_locks,
    _tip,
)
from tests.workflow.stages.question.question_real_git_test_support import (
    _run_git,
)

CLEANED = SurfaceOutcome.CLEANED
ABSENT = SurfaceOutcome.ABSENT
FAILED = SurfaceOutcome.FAILED

# The one destructive call, in the spelling the recorder notes it by: the head
# of its argv, matched whole so the reads this step takes under the same first
# word are not one of them.
_WORKTREE_REMOVE = "worktree remove"

_BRANCH_REFS = "refs/heads/"

# The local git runner every case that stands in front of one patches.
_HARDENED_SEAM = "_git_hardened"

# The cleanliness read a case stands in front of, the tip read that settles
# whose tree this is, and the ref update the racers in these cases run.
_CLEAN_SEAM = "_clean_worktree"

_TIP_SEAM = "_checkout_tip"

# The last of the holds asked about before the removal, which the case about
# what the tree hides arriving as late as anything can stands in front of.
_UNCHANGED_SEAM = "_registration_unchanged"

# The write that stages a lock, named here so a case can plant something at
# the name a derived one would have used.
_DERIVED_STAGING = "{0}.{1}.lock"

# What a file of somebody else's beside a lock says, for the cases about a
# staging name a write must not follow.
FOREIGN_CONTENT = "an operator's own file\n"

# A registration padded out past the bound, whose first bytes still read as
# this checkout's own.
OVERSIZED_TAIL = "x"

# Where a room on the way to this issue's branch is moved to, for the case
# about a namespace redirected wholesale.
MOVED_ROOM = "-elsewhere"

# The name a move that never happened leaves in the room a checkout is set
# aside inside, spelled as a pass that stopped would have left it.
_ASIDE_RESERVED = ".reclaiming-{0}-stopped"

# The buffer the short-write cases offer, and the descriptor they never reach:
# every call is answered by a stand-in, so nothing is written anywhere.
WHOLE_WRITE = b"abc"

WRITE_NOWHERE = -1

_UPDATE_REF = "update-ref"

# The anchor read a removal is settled by, which the case about a note moved
# between the reading and the deletion stands in front of, and the anchor
# write itself -- the one step left between the readings and the removal, and
# so the window every case about that window stands in.
_ANCHOR_READ_SEAM = "_anchored_commit"

_ANCHOR_SEAM = "_anchor_checkout"

# The read that opens a removal, which the case about ownership changing
# before the locks stands in front of.
_GITDIR_SEAM = "_checkout_gitdir"

# The naming of the checkout's own two locks, which is the last point at which
# this pass is holding nothing -- the window the case about a switched HEAD
# reaches into.
_OWN_LOCKS_SEAM = "_own_locks"

# The reading a registration's take-over spans, and the last question asked
# in front of the rename that ends it -- the window the cases about a
# registration rewritten under a take-over stand in.
_CHECKED_SEAM = "_registration_checked"

_STILL_SEAM = "_registration_still"

# The name a lock is taken to before it is read, which is the step the case
# about two passes reaching one leftover at once stands in front of, and the
# listing of what a stopped pass left aside.
_SCRATCH_SEAM = "_lock_scratch"

_ASIDE_SEAM = "_left_aside"

# The write that stages a lock before it is filed at its own name, which the
# case about a lock that never landed stands in front of.
_STAGED_SEAM = "_lock_staged"

# Where a checkout is moved to for the cases about a link left in its place,
# and what is left inside it so its survival is something a case can read.
MOVED_CHECKOUT = "moved-checkout"

MOVED_FILE = "someone-else-s-work.txt"

MOVED_CONTENT = "a tree nobody adjudicated\n"

# The file in a checkout's administrative directory that says where that
# checkout is, and what the cases about it put in its place: a file of
# somebody else's, and a decoy renamed over the name.
REGISTRATION = "gitdir"

FOREIGN_FILE = "somebody-else-s.txt"

FOREIGN_MODE = 0o640

DECOY_FILE = "decoy-gitdir"

# The mode a killed pass leaves behind on the registration, and the bit one is
# always given back.
HELD_MODE = 0o400

OWNER_WRITE = 0o200

# The mode a writer who put the write bits back leaves the registration in.
WRITABLE_FILE = 0o644

GIT_COMMAND = "git"

# The two argv words the fixtures reach for most: the command that moves a
# HEAD, and the flag every call here runs under.
CHECKOUT = "checkout"

QUIET = "-q"

# The command family the fixtures reach for directly: repairing a moved
# registration, and locking a checkout git then refuses to remove.
WORKTREE = "worktree"

# The branch a checkout is put on where a racer would, so nothing about it is
# this issue's any more while everything else still reads as clean.
OTHER_BRANCH = "somebody-else-s-branch"

# What a lock a killed pass left behind says inside it, and what one some
# command is holding right now says instead.
LEFT_BEHIND = f"{reclamation._LOCK_MARK} {{0}}\n"

HELD_BY_GIT = "ref: refs/heads/somewhere\n"

# The process a lock another live pass took names, for the case about two
# passes meeting one leftover: alive, so nothing reads it as stale again, and
# not this one, so what it wrote is not what this pass wrote.
TAKEN_BY_ANOTHER = os.getppid()

# The rule file, the path it hides, and what is in it, for the cases about a
# tree carrying something no status reports.
IGNORE_FILE = ".gitignore"

HIDDEN_FILE = "secrets.env"

HIDDEN_CONTENT = "TOKEN=an operator's own\n"

# The directory git cannot delete and the modes that make it so: an empty
# directory is invisible to every status, and a parent this process may not
# write in is one `remove_dir_recursively` stops inside.
STUCK_DIR = "stuck"

STUCK_INNER = "inner"

READ_ONLY_DIR = 0o500

WRITABLE_DIR = 0o700

RACED_MESSAGE = "raced"

# The branch a racer's commit is parked on, so what it holds is nameable
# without being anything this issue publishes under.
RACED_BRANCH = "-raced"

STRANDED_BRANCH = "-stranded"


def _registration_of(worktree: Path) -> Path:
    """The file in this checkout's git directory that says where it is."""
    return _index_path(worktree).parent / REGISTRATION


def _reaped() -> int:
    """One process id nothing on this host is running under any more."""
    ran = subprocess.Popen(
        [GIT_COMMAND, "--version"], stdout=subprocess.DEVNULL,
    )
    ran.wait()
    return ran.pid


def _mode(named: Path) -> int:
    """The permission bits one path carries, links not followed."""
    return S_IMODE(named.lstat().st_mode)


def _aiming_at(tree: Path) -> str:
    """What a registration says when it names one tree's own `.git`."""
    return f"{tree}/{GIT_FILE}\n"


def _read(moved: Path) -> str:
    """What one file in a tree this pass must not have taken still says."""
    return (moved / MOVED_FILE).read_text()


class _RacedCommit:
    """A commit landing in the window no reading covers.

    Installed in place of the last reading the removal is gated on: the tree
    answers clean, and a moment later it is carrying a commit that nothing but
    its own HEAD names. Standing in for that reading rather than patching a
    clock is what makes the race a case rather than a hope.
    """

    def __init__(self) -> None:
        self.made = ""

    def __call__(self, worktree: Path) -> ProbeAnswer:
        """Commit on no branch where a racer would, and answer clean."""
        _run_git(CHECKOUT, QUIET, "--detach", cwd=worktree)
        _run_git(
            "commit", QUIET, "--allow-empty", "-m", RACED_MESSAGE,
            cwd=worktree,
        )
        self.made = _tip(worktree, "HEAD")
        return ProbeAnswer.CONFIRMED


class _MovedCheckout:
    """A checkout renamed away and replaced by a link to where it went.

    What `worktree remove` follows. It resolves the path it is handed and
    deletes the REGISTERED tree at the far end, so once the registration has
    been repaired to the new location a link left in the checkout's place has
    the removal take a directory outside the tree this orchestrator owns --
    and every reading in front of it follows the link and agrees.

    Installed in place of one of those readings rather than raced against a
    real process, so the swap lands in a named window instead of a likely one.
    """

    def __init__(self, worktree: Path, elsewhere: Path, clone: Path) -> None:
        self.worktree = worktree
        self.elsewhere = elsewhere
        self.repaired = None
        self._clone = clone

    def __call__(self, *args, **options) -> ProbeAnswer:
        """Move the tree, point the registration at it, and link it back.

        The repair is the step the whole sequence turns on -- what comes down
        is the path the registration names -- so its status is kept rather
        than insisted on: a case run while that file is held still is one
        where git refuses it, and the answer says so.

        A file is left in the tree once it has moved, so what a case asserts
        about the far end is that its contents are still there rather than
        that some directory is. Written after the move, since a tree carrying
        it beforehand is one every reading in front of the removal refuses.
        """
        self.worktree.rename(self.elsewhere)
        (self.elsewhere / MOVED_FILE).write_text(MOVED_CONTENT)
        self.repaired = _ran_git(
            self._clone, WORKTREE, "repair", str(self.elsewhere),
        )
        self.worktree.symlink_to(self.elsewhere)
        return ProbeAnswer.CONFIRMED


class _StaleHandle:
    """A writer that opened the registration before this pass reached it.

    What a mode cannot answer. The handle is taken while the file is still
    git's own and writable, and everything done through it afterwards lands on
    whatever object that handle refers to -- which is the whole question the
    take-over is about.
    """

    def __init__(self, worktree: Path, elsewhere: Path) -> None:
        self.worktree = worktree
        self.elsewhere = elsewhere
        self.aimed_at = ""
        self.named = _registration_of(worktree)
        self.opened = os.open(self.named, os.O_WRONLY)

    def close(self) -> None:
        """Let the handle go, whatever the pass under test did."""
        os.close(self.opened)

    def swap(self) -> None:
        """Aim the handle at a tree of somebody's, and read the name back.

        What is recorded is what the NAME says once the write has happened,
        which is the whole of what the removal after it will be aimed by.
        """
        aimed = _aiming_at(self.elsewhere).encode()
        os.pwrite(self.opened, aimed, 0)
        os.ftruncate(self.opened, len(aimed))
        self.aimed_at = self.named.read_text()


class _Removals:
    """Every `worktree remove` a teardown made, in the order it made them.

    A wrapper rather than a stub -- the call still runs -- because what a case
    reads off it is whether the destructive step was reached at all, which
    only means something over a teardown that ran to its end.
    """

    def __init__(self) -> None:
        self.taken: list[str] = []
        self._ran_git = commands._git_hardened

    def __call__(self, *args: str, **options):
        """One local git call, noted when it is the one that destroys."""
        head = " ".join(args[:2])
        if head == _WORKTREE_REMOVE:
            self.taken.append(head)
        return self._ran_git(*args, **options)


class VerdictPermissionTest(_ReclaimTestCase):
    """What a verdict authorizes, and what it leaves exactly as it was."""

    def test_a_retained_candidate_is_left_alone(self) -> None:
        self.published()
        worktree = self.checkout()
        self.gh = _github(_terminal_issue(closed=False))

        reclaimed = self.spend(
            self.verdict(worktree=worktree, branches=self.branches),
        )

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertFalse(reclaimed.settled)
        self.assertTrue(worktree.is_dir())

    def test_the_artifacts_are_not_read_at_all(self) -> None:
        # The verdict is the whole of the permission, so a candidate it keeps
        # costs no git process here: a second opinion taken at this point
        # could disagree with the one that already refused.
        self.published()
        worktree = self.checkout()
        self.gh = _github(_terminal_issue(closed=False))
        kept = self.verdict(worktree=worktree, branches=self.branches)

        with patch.object(commands, _HARDENED_SEAM) as ran:
            self.spend(kept)
            ran.assert_not_called()

    def test_a_candidate_with_no_checkout_is_settled(self) -> None:
        # A surface an issue does not have is not one a teardown left
        # standing, and reporting it as one would leave a branch-only
        # candidate unable to ever come back settled.
        self.published()

        reclaimed = self.spend(self.verdict())

        self.assertEqual(self.outcomes(reclaimed), ())
        self.assertTrue(reclaimed.settled)

    def test_a_checkout_nothing_cleared_is_kept(self) -> None:
        # An eligible verdict that hands over no commit for the checkout it
        # names authorizes nothing about it: what the removal is measured
        # against is then nothing at all.
        self.published()
        worktree = self.checkout()
        proofless = ArtifactVerdict(
            _candidate(self.spec, ISSUE_NUMBER, worktree=worktree),
        )

        reclaimed = self.spend(proofless)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(worktree.is_dir())


class WholeCheckoutTest(_ReclaimTestCase):
    """The finished issue whose checkout the verdict cleared."""

    def test_the_checkout_of_a_finished_issue_goes(self) -> None:
        tip = self.published()
        worktree = self.checkout()

        reclaimed = self.spend(
            self.verdict(worktree=worktree, branches=self.branches),
        )

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(CLEANED))
        self.assertTrue(reclaimed.settled)
        self.assertFalse(worktree.exists())
        self.assertEqual(self.anchored(), "")
        self.assertEqual(_tip(self.clone, self.branch), tip)

    def test_a_second_pass_finds_nothing_to_take(self) -> None:
        # A checkout already gone is the ordinary shape of a retry, and
        # reporting it as a failure would keep the issue in a report forever
        # over an artifact nobody can find. Reported apart from the deletion
        # the first pass made, so nothing counts one checkout twice.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)

        first = self.spend(cleared)
        again = self.spend(cleared)

        self.assertEqual(self.outcomes(first), _checkout_surface(CLEANED))
        self.assertEqual(self.outcomes(again), _checkout_surface(ABSENT))
        self.assertTrue(again.settled)


class ArtifactOwnershipTest(_ReclaimTestCase):
    """Nothing outside the one path this issue's creators derive is touched."""

    def test_a_checkout_at_another_path_is_kept(self) -> None:
        # The path is checked against the one this issue's own creators
        # derive: what the verdict names here is a real checkout of this
        # orchestrator's, and it belongs to somebody else.
        self.published(_namespaced_branch(WIDGET_SLUG, OTHER_ISSUE_NUMBER))
        stranger = self.checkout(OTHER_ISSUE_NUMBER)
        cleared = ArtifactVerdict(
            _candidate(self.spec, ISSUE_NUMBER, worktree=stranger),
            proven=(ProvenTip(str(stranger), _tip(stranger, "HEAD")),),
        )

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(stranger.is_dir())

    def locating(self, artifacts, worktree: Path) -> Path | None:
        """Put the checkout on somebody else's branch, then answer as before.

        Installed in place of the read that opens the removal, which is the
        last step before the locks go on: everything the verdict was taken on
        has been read by then, and nothing is holding the tree yet.
        """
        _run_git(CHECKOUT, QUIET, OTHER_BRANCH, cwd=worktree)
        return self.located(artifacts, worktree)

    def test_a_checkout_switched_away_is_kept(self) -> None:
        # The window between the reading that cleared the tree and the locks
        # that hold it still. A checkout put on somebody else's branch there
        # is one every step after would take for ours -- the branch this pass
        # freezes is the one it moved onto, the anchor pins what that branch
        # stands on, and a clean tree on it reads clean -- so the whole
        # reading is taken again where nothing can move, and the identity is
        # what refuses.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        _run_git("branch", OTHER_BRANCH, cwd=worktree)
        self.located = reclamation._checkout_gitdir

        with patch.object(reclamation, _GITDIR_SEAM, self.locating):
            reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(worktree.is_dir())

    def test_a_link_where_a_checkout_belongs_is_kept(self) -> None:
        # `worktree remove` resolves the path it is handed and deletes the
        # registered tree at the far end, so a link left where this issue's
        # checkout belongs has it take a directory outside the tree this
        # orchestrator owns. Every reading in front of the removal follows the
        # link and agrees -- the repository, the branch its HEAD is on, the
        # tree carrying nothing loose -- which is why the mode of the path
        # itself is what refuses.
        self.published()
        worktree = self.checkout()
        elsewhere = self.world.path(MOVED_CHECKOUT)
        worktree.rename(elsewhere)
        _run_git(WORKTREE, "repair", str(elsewhere), cwd=self.clone)
        worktree.symlink_to(elsewhere)
        cleared = self.verdict(worktree=worktree, branches=self.branches)

        self.assertIs(
            evidence._checkout_identity(self.spec, ISSUE_NUMBER, worktree),
            ProbeAnswer.CONFIRMED,
        )

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(elsewhere.is_dir())
        self.assertTrue(worktree.is_symlink())


class DivergentWorkTest(_ReclaimTestCase):
    """Work made after the proof keeps the checkout holding it."""

    def test_a_commit_after_the_verdict_keeps_it(self) -> None:
        # The checkout is standing on a commit nothing cleared, so it may not
        # go: the tip is compared rather than merely resolved, which is what
        # makes work made after the proof survive.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        made = self.world.commit_on(self.clone, self.branch, start=self.branch)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(worktree.is_dir())
        self.assertEqual(_tip(self.clone, self.branch), made)

    def test_a_tree_written_in_since_keeps_it(self) -> None:
        # The proof said this tree was carrying nothing loose. It is not spent
        # on the tree that is there now.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        loose = _dirty(worktree)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(loose.exists())

    def racing(self, spec, worktree, issue_number: int) -> bool:
        """Pin the checkout, then write where a racer would.

        Installed in place of the anchor write, which is the one step left
        between the readings and the removal. Both ways a commit reaches this
        tree are tried there: one through its own HEAD, and one through the
        branch that HEAD resolves to -- which is a ref in the store the whole
        clone shares and answerable to neither lock the tree keeps. What the
        locks taken around all of it are for is that git refuses each of them.
        """
        anchored = self.anchoring(spec, worktree, issue_number)
        self.moved = _ran_git(
            self.clone, _UPDATE_REF, f"{_BRANCH_REFS}{self.branch}",
            self.world.commit_on(self.clone, f"{self.branch}{RACED_BRANCH}"),
        )
        self.raced = _ran_git(worktree, CHECKOUT, "--detach") or _ran_git(
            worktree, "commit", "--allow-empty", "-m", RACED_MESSAGE,
        )
        return anchored

    def test_work_raced_after_the_anchor_fails(self) -> None:
        # The window the anchor cannot cover on its own: a commit landing
        # between the note and the removal would be pinned by neither, and a
        # detached one is clean enough for a removal that does not force.
        #
        # Neither way in is open. Git takes `index.lock` and `HEAD.lock`
        # before it moves a HEAD or writes an index, and it takes the branch's
        # own lock before it writes that ref -- a checkout's HEAD is symbolic,
        # so what it stands on is whatever the branch under it stands on, and
        # that ref is reachable without going near the other two. All three
        # are this pass's for the duration.
        tip = self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.anchoring = obligations._anchor_checkout

        with patch.object(obligations, _ANCHOR_SEAM, self.racing):
            reclaimed = self.spend(cleared)

        self.assertNotEqual(self.raced, 0)
        self.assertNotEqual(self.moved, 0)
        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(CLEANED))
        self.assertEqual(cleared.proven[0].sha, tip)

    def test_a_commit_raced_into_the_window_is_kept(self) -> None:
        # The locks this teardown holds go on after the reading that cleared
        # the tree, and the window in front of them is one anybody can reach
        # into: a commit made there and left on no branch is clean, and every
        # step after it would read a tree that is no longer this issue's as
        # though it were. So the whole reading is taken again once the locks
        # are on, where nothing can move -- the tree is on no branch of this
        # issue's, and the removal does not run.
        #
        # The anchor is written before that recheck and holds what it found,
        # so what the raced commit ends up named by is the tree it is still
        # standing in and the note beside it both.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        racer = _RacedCommit()

        with patch.object(evidence, _CLEAN_SEAM, racer):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _checkout_surface(FAILED, FAILED),
        )
        self.assertTrue(worktree.is_dir())
        self.assertEqual(self.anchored(), racer.made)


class HeldBranchTest(_ReclaimTestCase):
    """The ref a removal freezes is the one the tree is standing on.

    An issue publishes under two names -- the slug-namespaced one and the
    legacy flat one -- and both read as its own, so which of them a checkout
    is on is a thing that can change while a pass is deciding what to hold.
    """

    def switching(self, gitdir: Path) -> tuple[Path, ...]:
        """Put the checkout on this issue's other published name.

        Installed in place of the naming of the checkout's own two locks,
        which is the last point at which nothing is held yet: an issue
        publishes under two names and both read as its own, so everything
        after this reads the tree as ours whichever it is standing on, and
        only what HEAD is read as says which ref gets frozen.
        """
        named = self.naming(gitdir)
        _run_git(CHECKOUT, QUIET, self.legacy, cwd=self.worktree)
        return named

    def moving(self, *args: str, **options):
        """Advance the branch the checkout really stands on, at the removal.

        The one window a lock on the wrong ref would leave open: every reading
        has been taken by then, and what is left between them and the command
        is exactly what the branch's own lock is held for.
        """
        if " ".join(args[:2]) == _WORKTREE_REMOVE:
            self.moved = _ran_git(
                self.clone, _UPDATE_REF, f"{_BRANCH_REFS}{self.legacy}",
                self.world.commit_on(
                    self.clone, f"{self.branch}{RACED_BRANCH}",
                ),
            )
        return self.hardened(*args, **options)

    def test_a_switched_head_freezes_its_own_branch(self) -> None:
        # Which ref to freeze is read off HEAD, and a HEAD read before
        # `HEAD.lock` is this pass's is one that can move afterwards: a
        # checkout switched between this issue's two published names in that
        # window would have this pass holding the ref it moved off while the
        # ref it moved onto stayed free to move. Read once the lock is on, the
        # ref that gets frozen is the one the tree is actually standing on.
        tip = self.published()
        self.legacy = _legacy_branch(ISSUE_NUMBER)
        _branch_at(self.clone, self.legacy, self.branch)
        self.worktree = self.checkout()
        cleared = self.verdict(
            worktree=self.worktree, branches=self.branches,
        )
        self.naming = reclamation._own_locks
        self.hardened = commands._git_hardened

        with patch.object(
            reclamation, _OWN_LOCKS_SEAM, self.switching,
        ), patch.object(commands, _HARDENED_SEAM, self.moving):
            reclaimed = self.spend(cleared)

        self.assertNotEqual(self.moved, 0)
        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(CLEANED))
        self.assertEqual(_tip(self.clone, self.legacy), tip)


class LateChangeTest(_ReclaimTestCase):
    """What arrives after the reading the step ahead of it ran on.

    Each case is one window: between a probe and the destructive step it
    gates. The lock this pass holds is its own and git's own locks stop
    commits rather than writes, so each of those windows is one another hand
    can reach into.
    """

    def hiding(self, spec, worktree: Path, issue_number: int) -> bool:
        """Pin the checkout, then leave a hidden file where a writer would.

        Installed in place of the anchor write, which is the last step before
        the removal: git's own locks stop a `commit` in that tree and stop
        nothing at all from writing in it, and what the rules cover is what
        `worktree remove` takes without a word.
        """
        anchored = self.anchoring(spec, worktree, issue_number)
        (worktree / HIDDEN_FILE).write_text(HIDDEN_CONTENT)
        return anchored

    def test_an_ignored_file_written_since_keeps_it(self) -> None:
        # The one thing git does not refuse for itself. `worktree remove`
        # stops over an untracked or modified file and takes an ignored one
        # without a word, so a checkout carrying nothing else passes every
        # other reading here -- and what a repository calls derived is still
        # somebody's `.env` when an unattended pass is the one deleting it.
        _track_file(self.clone, IGNORE_FILE, f"{HIDDEN_FILE}\n")
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        hidden = worktree / HIDDEN_FILE
        hidden.write_text(HIDDEN_CONTENT)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(hidden.read_text(), HIDDEN_CONTENT)

    def test_a_file_hidden_while_held_keeps_it(self) -> None:
        # The same file, arriving in the window the locks were supposed to
        # close. They close what git takes them for -- a commit, a checkout, a
        # reset -- and a write is none of those, so the reading that cleared
        # the tree is stale by the time the removal runs. Retaken one process
        # before it, the file is found; the other probe goes on reporting the
        # tree clean, which is what the retaken one is there for.
        _track_file(self.clone, IGNORE_FILE, f"{HIDDEN_FILE}\n")
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.anchoring = obligations._anchor_checkout

        with patch.object(obligations, _ANCHOR_SEAM, self.hiding):
            reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertIs(
            evidence._clean_worktree(worktree), ProbeAnswer.CONFIRMED,
        )
        self.assertEqual(
            (worktree / HIDDEN_FILE).read_text(), HIDDEN_CONTENT,
        )


class RegistrationHoldTest(_ReclaimTestCase):
    """The file that decides where the destruction lands, and what holds it.

    `worktree remove` is handed a path, but the path only selects a
    registration and the registration names the tree that comes down -- so
    every way that file can stop meaning what this pass established it meant
    is a way the removal can be aimed somewhere nobody adjudicated.
    """

    def replacing(self, worktree: Path) -> BranchTip:
        """Rename a file of somebody's over the registration, and read as before.

        Where taking the write bits off reaches its limit: the file itself
        cannot be rewritten, and the NAME can be replaced through the
        directory above it, which leaves this pass holding an object the
        removal will never read -- and a writable one at that name for the
        next command to rewrite. What is written says exactly what the file
        it replaces says, so nothing but the object itself gives it away.

        Installed in place of the tip read, which is one of the readings that
        settle whose tree this is -- and so one of the ones the registration
        is asked about after.
        """
        registration = _registration_of(worktree)
        decoy = self.world.path(DECOY_FILE)
        decoy.write_text(registration.read_text())
        decoy.rename(registration)
        return self.reading(worktree)

    def rewriting(self, spec, worktree: Path, issue_number: int) -> bool:
        """Pin the checkout, then rewrite the registration in place.

        Installed in place of the anchor write, which is one step ahead of the
        last reading: what is put back at the same name is a file naming a
        tree somewhere else, so nothing about the NAME gives it away and only
        what it says has changed.
        """
        anchored = self.anchoring(spec, worktree, issue_number)
        elsewhere = self.world.path(MOVED_CHECKOUT)
        named = _registration_of(worktree)
        named.chmod(WRITABLE_FILE)
        named.write_text(_aiming_at(elsewhere))
        return anchored

    def swapped(self, *args: str, **options):
        """Rewrite the registration through the old handle, at the removal."""
        if " ".join(args[:2]) == _WORKTREE_REMOVE:
            self.writer.swap()
        return self.hardened(*args, **options)

    def test_a_linked_registration_is_refused(self) -> None:
        # The file that aims the removal is one an agent can replace with a
        # link, and every read and write through that name would then be about
        # whatever it points at -- including the one taking the write bits
        # off, which is a mode this pass could never give back once the
        # removal had deleted the link. The far end says exactly what a
        # registration for this checkout says, so nothing about its contents
        # gives it away: what refuses is opening the name without following
        # it, and nobody else's file is touched.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        foreign = self.world.path(FOREIGN_FILE)
        foreign.write_text(_aiming_at(worktree))
        foreign.chmod(FOREIGN_MODE)
        registration = _registration_of(worktree)
        registration.unlink()
        registration.symlink_to(foreign)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(_mode(foreign), FOREIGN_MODE)
        self.assertTrue(worktree.is_dir())

    def test_a_registration_replaced_is_refused(self) -> None:
        # The half a mode cannot hold. A rename through the writable directory
        # above puts a new file at the name while the object this pass holds
        # open goes on being the old one -- so the name is read once more and
        # compared against what is held, and the destructive call is never
        # made at all rather than made and refused by git.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        watched = _Removals()
        self.reading = evidence._checkout_tip

        with patch.object(
            evidence, _TIP_SEAM, self.replacing,
        ), patch.object(commands, _HARDENED_SEAM, watched):
            reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(watched.taken, [])
        self.assertTrue(worktree.is_dir())

    def test_a_registration_rewritten_is_refused(self) -> None:
        # A rename is not the only way that file stops meaning what it meant.
        # Anybody who puts the write bits back can rewrite it where it stands,
        # which leaves the name resolving to the very object this pass holds
        # while what it says -- the whole of what decides where the
        # destruction lands -- is somewhere else. So the contents are read
        # back through the held descriptor, not just the identity of the name.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.anchoring = obligations._anchor_checkout
        watched = _Removals()

        with patch.object(
            obligations, _ANCHOR_SEAM, self.rewriting,
        ), patch.object(commands, _HARDENED_SEAM, watched):
            reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(watched.taken, [])
        self.assertTrue(worktree.is_dir())

    def test_an_older_handle_cannot_aim_the_removal(self) -> None:
        # Taking the write bits off a file says nothing to somebody who opened
        # it before they came off, and the window that handle can write in
        # ends only when the command reads the file -- after every reading
        # this pass can take. So the file is not merely read and held: a copy
        # of this pass's own, saying exactly what the original said, is
        # renamed over the name, which leaves every handle opened earlier
        # pointing at an inode nothing is filed at. What the removal is aimed
        # by is therefore untouched, and the checkout comes down.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.writer = _StaleHandle(worktree, self.world.path(MOVED_CHECKOUT))
        self.addCleanup(self.writer.close)
        self.hardened = commands._git_hardened

        with patch.object(commands, _HARDENED_SEAM, self.swapped):
            reclaimed = self.spend(cleared)

        self.assertNotIn(MOVED_CHECKOUT, self.writer.aimed_at)
        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(CLEANED))
        self.assertFalse(self.writer.elsewhere.exists())


class TakeOverSeamTest(_ReclaimTestCase):
    """The window between reading a registration and filing a copy over it.

    What the take-over files is a copy of what the original SAID, so anything
    that rewrites the original in that window is something this pass would
    otherwise write over -- including `git worktree move`, whose whole job is
    to record where a checkout went.
    """

    def moving(self, named: Path, opened: int, says: str) -> bool:
        """Ask as the take-over does, then move the checkout for real.

        Installed in place of the last question in front of the rename, which
        is the window nothing can close from in front of it: what the answer
        establishes is a step old by the time the rename runs.
        """
        still = self.asking(named, opened, says)
        self.moved = _ran_git(
            self.clone, WORKTREE, "move",
            str(self.worktree), str(self.elsewhere),
        )
        return still

    def rewriting(self, named: Path, opened: int, says: str) -> bool:
        """Ask as the take-over does, then write through an older handle."""
        still = self.asking(named, opened, says)
        aimed = _aiming_at(self.elsewhere).encode()
        os.pwrite(self.older, aimed, 0)
        os.ftruncate(self.older, len(aimed))
        return still

    def prepared(self) -> Path:
        """This issue's checkout, with everything these cases read set up."""
        self.published()
        self.worktree = self.checkout()
        self.registration = _registration_of(self.worktree)
        self.elsewhere = self.world.path(MOVED_CHECKOUT)
        return self.worktree

    def spending(self, standing):
        """Run one teardown with `standing` in place of the last question."""
        cleared = self.verdict(
            worktree=self.worktree, branches=self.branches,
        )
        self.asking = reclamation._registration_still
        with patch.object(reclamation, _STILL_SEAM, standing):
            return self.spend(cleared)

    def test_a_move_mid_take_over_is_put_back(self) -> None:
        # A real `git worktree move` finishing in that window records where it
        # put the checkout, and the rename after it files what the file used
        # to say over what it now says. What was displaced is still readable
        # through the descriptor it displaced, so git's own record goes back
        # at the name and the removal does not run.
        self.prepared()

        reclaimed = self.spending(self.moving)

        self.assertEqual(self.moved, 0)
        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(
            self.registration.read_text(), _aiming_at(self.elsewhere),
        )
        self.assertTrue((self.elsewhere / GIT_FILE).exists())

    def test_a_handle_writing_mid_take_over_is_kept(self) -> None:
        # The same window reached through a descriptor somebody opened while
        # the file still had its write bits, which is what no mode answers.
        self.prepared()
        self.older = os.open(self.registration, os.O_WRONLY)
        self.addCleanup(os.close, self.older)

        reclaimed = self.spending(self.rewriting)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(
            self.registration.read_text(), _aiming_at(self.elsewhere),
        )
        self.assertTrue(self.worktree.is_dir())


class MovedCheckoutTest(_ReclaimTestCase):
    """A path that stops being the tree it named, at two different moments.

    `worktree remove` takes a path and resolves it, so what the removal
    destroys is wherever the path leads rather than the path itself. Both
    cases below move the tree away and leave a link behind; what separates
    them is which side of the last reading the swap lands on.
    """

    def swapping(self, worktree: Path) -> _MovedCheckout:
        """The swap, ready to stand in for whichever reading a case names."""
        return _MovedCheckout(
            worktree, self.world.path(MOVED_CHECKOUT), self.clone,
        )

    def test_a_tree_moved_before_the_read_is_kept(self) -> None:
        # The window the early type check leaves open: everything from that
        # check to the removal, which is where a rename, a repair, and a link
        # fit comfortably. What is asked once the locks are on is where the
        # path leads rather than how it is spelled, and the registration the
        # removal is aimed by no longer names the tree this path is.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        moved = self.swapping(worktree)

        with patch.object(evidence, _CLEAN_SEAM, moved):
            reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(moved.repaired, 0)
        self.assertEqual(_read(moved.elsewhere), MOVED_CONTENT)
        self.assertTrue(worktree.is_symlink())


class ConcurrentPassTest(_ReclaimTestCase):
    """Two passes over one clone, reaching for the same lock at once.

    Neither is holding anything the other has to queue for: the target-root
    lock is process-local and a lock file is a name in a directory both can
    write. So every hold is bound to the exact file this pass created or read,
    and what the other pass left at that name is left where it is.
    """

    def replacing(self, spec, worktree: Path, issue_number: int) -> bool:
        """Pin the checkout, then put another pass's lock where this one's is.

        Installed in place of the anchor write, one step ahead of the last
        reading: nothing about creating a lock file stops somebody removing it
        afterwards, and what stands at the name from then on is a live lock
        this pass never took.
        """
        anchored = self.anchoring(spec, worktree, issue_number)
        self.snatched = _removal_locks(self.clone, worktree, self.branch)[0]
        self.snatched.unlink()
        self.snatched.write_text(HELD_BY_GIT)
        return anchored

    def snatching(self, lock: Path):
        """Answer that the lock is a leftover, then let another pass take it.

        Installed in place of the staleness reading, which is the window two
        passes meeting one leftover share: both see the same file, and by the
        time the second gets to the deletion that reading allows, the first
        has taken the leftover away and created a live lock of its own.
        """
        was = self.reading(lock)
        if was is not None:
            self.snatched = lock
            lock.unlink()
            lock.write_text(LEFT_BEHIND.format(TAKEN_BY_ANOTHER))
        return was

    def test_a_lock_swapped_since_it_was_taken_stops(self) -> None:
        # A lock is a name in a directory an agent can write, and a name that
        # no longer resolves to the file this pass created is a checkout
        # something else is free to be committing in. So each one is asked
        # again immediately before the removal -- and the one at that name
        # afterwards is somebody's to give back, not this pass's.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.anchoring = obligations._anchor_checkout

        with patch.object(obligations, _ANCHOR_SEAM, self.replacing):
            reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(self.snatched.read_text(), HELD_BY_GIT)
        self.assertTrue(worktree.is_dir())

    def snatching_late(self, lock: Path):
        """Let another pass take the leftover, then name where this takes it.

        Installed in place of the naming that runs between the reading and the
        take, which is the window a reading in front of a delete leaves open:
        by the time the delete would run, what is at the name is a live lock
        another pass has just made.
        """
        self.snatched = lock
        lock.unlink()
        lock.write_text(LEFT_BEHIND.format(TAKEN_BY_ANOTHER))
        return self.naming(lock)

    def test_a_lock_swapped_under_a_take_is_kept(self) -> None:
        # Reading a name and then unlinking it is two steps, and a lock made
        # in between is one the unlink would delete. So the take comes first
        # and the reading second: what this ends up holding is one object, and
        # a lock that turns out to be somebody's goes back where it was.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        left = _removal_locks(self.clone, worktree, self.branch)[0]
        left.write_text(LEFT_BEHIND.format(_reaped()))
        self.naming = reclamation._lock_scratch

        with patch.object(reclamation, _SCRATCH_SEAM, self.snatching_late):
            reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(
            self.snatched.read_text(), LEFT_BEHIND.format(TAKEN_BY_ANOTHER),
        )
        self.assertTrue(worktree.is_dir())

    def test_a_stale_lock_another_pass_took_is_kept(self) -> None:
        # Deleting by name is what would make two passes over one leftover
        # both go on: each would remove what the other had just created, and
        # each would then take a lock neither of them holds. Bound to the
        # object the staleness was read on, the second pass finds a different
        # file at that name and refuses instead.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        left = _removal_locks(self.clone, worktree, self.branch)[0]
        left.write_text(LEFT_BEHIND.format(_reaped()))
        self.reading = reclamation._left_behind

        with patch.object(reclamation, "_left_behind", self.snatching):
            reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(
            self.snatched.read_text(), LEFT_BEHIND.format(TAKEN_BY_ANOTHER),
        )
        self.assertTrue(worktree.is_dir())


class AnotherPassTest(_ReclaimTestCase):
    """What a pass that is not this one left behind, or already did.

    The holds this teardown takes are files and a file mode, and it gives them
    back through callbacks nothing runs when a process is killed. So a later
    pass meets its own leftovers, and has to tell them from a command that is
    holding the same names right now -- and it meets a checkout another pass
    has already taken, which is the success absent is everywhere else here.
    """

    def removing(self, *args: str, **options):
        """Let another pass take the checkout first, then run this one's."""
        if " ".join(args[:2]) == _WORKTREE_REMOVE:
            _run_git(*args, cwd=self.clone)
        return self.hardened(*args, **options)

    def test_locks_a_killed_pass_left_are_taken(self) -> None:
        # Nothing runs when a process is killed, so the files this pass takes
        # for the length of a removal outlive it -- and every later pass would
        # read them as a command still running and refuse this issue for good.
        # What each says inside it is which process took it, so a leftover is
        # one this host recognises and takes again.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        for lock in _removal_locks(self.clone, worktree, self.branch):
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text(LEFT_BEHIND.format(_reaped()))

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(CLEANED))
        self.assertTrue(reclaimed.settled)

    def test_a_lock_somebody_holds_is_left_alone(self) -> None:
        # The other half of the same reading, and the reason it is not simply
        # a matter of clearing what is in the way: a lock carrying anything
        # but this host's mark is one a git command is holding at this moment,
        # and taking it from under that command would corrupt what it is
        # doing.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        held = _removal_locks(self.clone, worktree, self.branch)[0]
        held.write_text(HELD_BY_GIT)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertEqual(held.read_text(), HELD_BY_GIT)
        self.assertTrue(worktree.is_dir())

    def test_a_registration_left_held_comes_back(self) -> None:
        # The mode is the other thing a killed pass leaves, and restoring what
        # was found would make it permanent -- with `worktree repair` and
        # `worktree move` for that checkout along with it. Git writes this
        # file owner-writable, so a mode without that bit is this host's own
        # hold rather than anybody's choice.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        registration = _registration_of(worktree)
        registration.chmod(HELD_MODE)
        _ran_git(self.clone, WORKTREE, "lock", str(worktree))

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(_mode(registration) & OWNER_WRITE)

    def staging(self, lock: Path, marked: str) -> Path:
        """Stage the lock and stop there, as a killed pass would.

        The staging file is written and never linked, which is what a process
        killed in that window leaves: a file under a name nothing reads, and
        nothing at all at the name the lock is for.
        """
        self.staged = self.writing(lock, marked)
        raise OSError("the pass stopped here")

    def test_a_lock_that_never_landed_leaves_nothing(self) -> None:
        # A lock is written whole under a name of its own and then linked to
        # the one it is for, so a write that failed -- or a pass that stopped
        # in that window -- leaves nothing at the lock's own name. Created
        # first and marked after, what it would leave is a file carrying
        # nothing, which no later pass can recognise as this host's: it reads
        # as a command's, is never taken again, and refuses this issue for
        # good. The pass after this one finishes instead, over the staging
        # file the stopped one never cleaned up.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        held = _removal_locks(self.clone, worktree, self.branch)[0]
        self.writing = reclamation._lock_staged

        with patch.object(reclamation, _STAGED_SEAM, self.staging):
            stopped = self.spend(cleared)

        self.assertEqual(self.outcomes(stopped), _checkout_surface(FAILED))
        self.assertFalse(held.exists())
        self.assertTrue(self.staged.exists())

        finished = self.spend(cleared)

        self.assertEqual(self.outcomes(finished), _checkout_surface(CLEANED))
        self.assertFalse(worktree.exists())

    def test_a_checkout_another_pass_took_is_absent(self) -> None:
        # Two passes over one host, and the other got there first. The command
        # refuses a path it can no longer find a working tree at, which is
        # this removal having happened without it -- the success every other
        # absence in this domain is, and reported apart from a deletion this
        # pass made so nothing counts one checkout twice.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.hardened = commands._git_hardened

        with patch.object(commands, _HARDENED_SEAM, self.removing):
            reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(ABSENT))
        self.assertTrue(reclaimed.settled)
        self.assertFalse(worktree.exists())


class SpecialFileTest(_ReclaimTestCase):
    """A name an agent left something unreadable at answers rather than waits.

    Two of the names this pass reads are names anything may be put at, and
    both are read while it is holding the target root and git's own locks for
    this checkout. A read that blocks there never comes back to give any of
    them up, so every one of these opens refuses to follow, refuses to wait,
    and asks the descriptor what it is before it asks what it says.
    """

    def test_a_fifo_at_the_registration_is_refused(self) -> None:
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        registration = _registration_of(worktree)
        registration.unlink()
        os.mkfifo(registration)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(worktree.is_dir())

    def test_a_fifo_at_a_lock_is_refused(self) -> None:
        # A lock this pass cannot read is one it leaves alone, and a fifo is
        # the shape that answers the open and then blocks whoever reads it --
        # so what it is is established off the descriptor rather than off what
        # comes out of it.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        held = _removal_locks(self.clone, worktree, self.branch)[0]
        os.mkfifo(held)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(held.is_fifo())
        self.assertTrue(worktree.is_dir())


class CommandSeamTest(_ReclaimTestCase):
    """The window between the last reading and the command that resolves a path.

    `worktree remove` deletes the path its registration names and resolves it
    at the moment it runs, so every reading this pass takes is about what that
    name meant beforehand. What closes the window is that the name stops being
    the checkout's before the command runs at all: the tree is moved, inside
    its own room, to a name this pass makes and nobody was told, and the
    registration -- which nothing else can write -- is aimed at where it went.
    Whatever arrives at the old name after that arrives at a path this
    teardown has finished with.
    """

    def arriving(self, *args: str, **options):
        """Put a checkout of somebody's where this issue's used to be."""
        if " ".join(args[:2]) == _WORKTREE_REMOVE:
            self.worktree.mkdir(parents=True, exist_ok=True)
            (self.worktree / GIT_FILE).write_text(_aiming_at(self.worktree))
            (self.worktree / HIDDEN_FILE).write_text(HIDDEN_CONTENT)
        return self.hardened(*args, **options)

    def hiding(self, *args: str, **options):
        """Leave a file the repository's own rules hide at the old name."""
        if " ".join(args[:2]) == _WORKTREE_REMOVE:
            self.worktree.mkdir(parents=True, exist_ok=True)
            (self.worktree / HIDDEN_FILE).write_text(HIDDEN_CONTENT)
        return self.hardened(*args, **options)

    def renaming(self, *args: str, **options):
        """Try to move whatever is at the old name out from under the command."""
        if " ".join(args[:2]) == _WORKTREE_REMOVE:
            self.moved = _ran_git(
                self.clone, WORKTREE, "list", "--porcelain",
            )
            self.swapped = self.worktree.exists()
        return self.hardened(*args, **options)

    def spending(self, standing) -> None:
        """Run one teardown with `standing` in place of the local runner."""
        _track_file(self.clone, IGNORE_FILE, f"{HIDDEN_FILE}\n")
        self.published()
        self.worktree = self.checkout()
        cleared = self.verdict(
            worktree=self.worktree, branches=self.branches,
        )
        self.hardened = commands._git_hardened
        with patch.object(commands, _HARDENED_SEAM, standing):
            self.reclaimed = self.spend(cleared)

    def test_the_path_is_no_longer_the_checkout_s(self) -> None:
        # The name the command would have been pointed at is not the tree by
        # the time the command runs: this pass took the tree out of reach of
        # it first, which is the whole of what closes the window.
        self.spending(self.renaming)

        self.assertFalse(self.swapped)
        self.assertEqual(
            self.outcomes(self.reclaimed), _checkout_surface(CLEANED),
        )

    def test_a_checkout_at_the_old_name_is_kept(self) -> None:
        # A tree somebody puts where this issue's used to be is one the
        # command never reaches: it is aimed where this pass moved the
        # checkout to, so what arrives at the old name -- and everything the
        # repository's rules hide inside it -- is untouched.
        self.spending(self.arriving)

        self.assertEqual(
            self.outcomes(self.reclaimed), _checkout_surface(CLEANED),
        )
        self.assertTrue(self.worktree.is_dir())
        self.assertEqual(
            (self.worktree / GIT_FILE).read_text(), _aiming_at(self.worktree),
        )
        self.assertEqual(
            (self.worktree / HIDDEN_FILE).read_text(), HIDDEN_CONTENT,
        )

    def test_a_file_hidden_at_the_old_name_is_kept(self) -> None:
        # The one reading git does not make for itself is the one no reading
        # in front of the command can be later than: an ignored path is what
        # `worktree remove` takes without a word. What answers it is that the
        # tree the command deletes is not the tree anybody can reach by name.
        self.spending(self.hiding)

        self.assertEqual(
            self.outcomes(self.reclaimed), _checkout_surface(CLEANED),
        )
        self.assertEqual(
            (self.worktree / HIDDEN_FILE).read_text(), HIDDEN_CONTENT,
        )


class StagedLockTest(_ReclaimTestCase):
    """What a lock is written under before it is filed at the name it is for.

    A staging name anybody can derive is a name anybody can plant something
    at, and the write that follows one would put this host's mark wherever it
    led -- or wait forever on something that never answers, with the target
    root and git's own locks already held.
    """

    def planted(self, worktree: Path) -> Path:
        """The name a staging file derived from a lock would have taken.

        Beside the lock git takes for the branch, which is the one of the
        three that lives in the store the clone keeps: what is planted there
        outlives the removal, so a case can say afterwards that nothing here
        touched it.
        """
        lock = _removal_locks(self.clone, worktree, self.branch)[-1]
        return lock.with_name(_DERIVED_STAGING.format(lock.name, os.getpid()))

    def test_a_link_at_a_derived_name_is_not_written(self) -> None:
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        foreign = self.world.path(FOREIGN_FILE)
        foreign.write_text(FOREIGN_CONTENT)
        staged = self.planted(worktree)
        staged.symlink_to(foreign)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(CLEANED))
        self.assertEqual(foreign.read_text(), FOREIGN_CONTENT)
        self.assertTrue(staged.is_symlink())

    def test_a_fifo_at_a_derived_name_is_not_opened(self) -> None:
        # A write that opened one would wait for a reader that never comes,
        # holding the target root and both of the checkout's own locks for as
        # long as it waited.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        waiting = self.planted(worktree)
        os.mkfifo(waiting)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(CLEANED))
        self.assertTrue(waiting.is_fifo())


class IndirectRefTest(_ReclaimTestCase):
    """A branch standing for another name is one no lock at it holds still.

    Git reads a ref two ways this pass has to care about: a loose file that IS
    a filesystem link, and one whose contents name another ref. Either way an
    `update-ref` on this issue's branch moves the ref at the far end, and the
    lock this pass would take is at the near one.
    """

    def elsewhere(self, tip: str) -> str:
        """A branch of somebody else's, standing where this issue's does."""
        other = f"{self.branch}{OTHER_BRANCH}"
        _branch_at(self.clone, other, tip)
        return f"{_BRANCH_REFS}{other}"

    def loose(self, ref: str | None = None) -> Path:
        """Where one branch is filed as a file of its own under this clone."""
        ref = ref or f"{_BRANCH_REFS}{self.branch}"
        return self.clone / GIT_FILE / ref

    def linked(self, tip: str) -> None:
        """Leave this issue's branch as a link onto somebody else's."""
        aimed = self.loose(self.elsewhere(tip))
        loose = self.loose()
        loose.unlink()
        loose.symlink_to(aimed)

    def test_a_ref_linked_at_another_is_refused(self) -> None:
        # Git reads a ref that IS a filesystem link by following it, so this
        # issue's branch and somebody else's are one file -- and the lock an
        # `update-ref` on the far name takes is not the one at this name.
        tip = self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.linked(tip)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(worktree.is_dir())

    def test_a_room_on_the_way_to_a_ref_is_refused(self) -> None:
        # Git walks every room on the way to a ref, not only the last step, so
        # a namespace replaced with a link files this issue's branch somewhere
        # this pass never looked -- and every listing of that namespace
        # answers for whatever is at the far end. Asked of the lock itself,
        # since what a room redirected wholesale costs is not one reading.
        self.published()
        worktree = self.checkout()
        rooms = self.loose().parent
        moved = rooms.with_name(f"{rooms.name}{MOVED_ROOM}")
        rooms.rename(moved)
        rooms.symlink_to(moved)

        self.assertIsNone(
            reclamation._branch_lock(
                _candidate(self.spec, ISSUE_NUMBER, worktree=worktree),
                worktree,
            ),
        )


class BoundedReadingTest(_ReclaimTestCase):
    """What is read is read to a bound, and what is past it is refused."""

    def test_an_oversized_registration_is_refused(self) -> None:
        # Read only as far as the bound, a file padded so its first bytes
        # strip to this checkout's own path passes every comparison here --
        # and the take-over then files that truncation at the name, throwing
        # away whatever the rest of it was.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        registration = _registration_of(worktree)
        padded = _aiming_at(worktree).ljust(
            reclamation._REGISTRATION_LIMIT,
        )
        registration.write_text(f"{padded}{OVERSIZED_TAIL}")

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(worktree.is_dir())
        self.assertTrue(registration.read_text().endswith(OVERSIZED_TAIL))


class WholeWriteTest(unittest.TestCase):
    """A write that takes less than it was given is offered the rest.

    What `os.write` answers is how much it took, and a caller reading that as
    "done" files half a registration or a lock carrying a mark nothing can
    recognise -- which is a lock that refuses its issue for good.
    """

    def short(self, writing: int, written: bytes) -> int:
        """Take one byte of whatever was offered, and say so."""
        self.offered.append(bytes(written))
        return 1

    def test_what_a_short_write_left_is_written_again(self) -> None:
        self.offered: list[bytes] = []

        with patch.object(reclamation.os, "write", self.short):
            reclamation._written_whole(WRITE_NOWHERE, WHOLE_WRITE)

        self.assertEqual(self.offered, [b"abc", b"bc", b"c"])

    def test_a_write_that_takes_nothing_is_refused(self) -> None:
        with patch.object(
            reclamation.os, "write", return_value=0,
        ), self.assertRaises(OSError):
            reclamation._written_whole(WRITE_NOWHERE, WHOLE_WRITE)


class StepFailureTest(_ReclaimTestCase):
    """A removal that could not finish leaves the checkout standing."""

    def stuck(self, worktree: Path) -> Path:
        """Leave one directory in this checkout that git cannot delete.

        What makes `worktree remove` fail HALFWAY rather than refuse. An empty
        directory is invisible to every status, so nothing about the tree
        reads as dirty and the removal is attempted; a parent this process may
        not write in is one the recursive delete stops inside. Git takes what
        it can, says so, and goes on to delete the administrative directory
        anyway -- which is what leaves a checkout whose HEAD and reflog are
        gone while the surface reports failure.
        """
        stuck = worktree / STUCK_DIR
        (stuck / STUCK_INNER).mkdir(parents=True)
        stuck.chmod(READ_ONLY_DIR)
        self.addCleanup(stuck.chmod, WRITABLE_DIR)
        return stuck

    def test_a_checkout_git_will_not_remove_stays(self) -> None:
        # A locked worktree is a removal git refuses without `--force`, and
        # forcing is exactly what this teardown does not do.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        _ran_git(self.clone, WORKTREE, "lock", str(worktree))

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(worktree.is_dir())

    def test_a_removal_that_stopped_halfway_is_failed(self) -> None:
        # The step ran and did not finish, which is told from one that never
        # ran by the path it named: a command that came back non-zero over a
        # path still standing is the failure it says it is. The note is
        # measured all the same, and what it pins is the commit this verdict
        # cleared, so it goes and only the surface carries the failure.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        stuck = self.stuck(worktree)
        watched = _Removals()

        with patch.object(commands, _HARDENED_SEAM, watched):
            reclaimed = self.spend(cleared)

        self.assertEqual(watched.taken, [_WORKTREE_REMOVE])
        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(stuck.exists())
        self.assertEqual(self.anchored(), "")


class AnchorReconciliationTest(_ReclaimTestCase):
    """What becomes of the commit a removal pinned, on this pass and after.

    An anchor outlives the checkout it was taken from, so a note left standing
    is a teardown that has left something behind -- and one nobody could take
    away stands in front of every removal for this issue until somebody
    settles it.
    """

    def repointing(self, spec, issue_number: int) -> str:
        """Read the anchor, then move it where a racer would.

        Installed in place of the read the discard is decided on, which is the
        window the lease exists for: what the caller acts on is the commit it
        read, and by the time the deletion runs the note is holding somebody
        else's. Nothing happens before there is a note to move, so the read
        the removal is gated on still answers for an issue with none.
        """
        ref = obligations._anchor_ref(spec, issue_number)
        anchored = obligations._note_at(spec, ref)
        if anchored:
            self.repointed = self.world.commit_on(
                self.clone, f"{self.branch}{RACED_BRANCH}",
            )
            _run_git(_UPDATE_REF, ref, self.repointed, cwd=self.clone)
        return anchored

    def test_an_anchor_moved_since_the_read_is_kept(self) -> None:
        # The store these notes live in is one the agents this orchestrator
        # runs can write, so an anchor can be repointed between the read that
        # cleared it and the deletion that read allows. What it is repointed
        # at is a commit nobody established anything about -- which is the
        # very thing an anchor exists to hold -- so the deletion states what
        # it expects and git refuses it.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)

        with patch.object(obligations, _ANCHOR_READ_SEAM, self.repointing):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _checkout_surface(FAILED, FAILED),
        )
        self.assertFalse(worktree.exists())
        self.assertEqual(self.anchored(), self.repointed)

    def test_a_note_that_would_not_go_is_not_settled(self) -> None:
        # The checkout is gone and the note over it is not, which is a
        # teardown that has left something behind: reported settled, the note
        # would be left with nothing naming it.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)

        with patch.object(
            obligations, "_discard_anchor", return_value=False,
        ):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _checkout_surface(FAILED, FAILED),
        )
        self.assertFalse(reclaimed.settled)
        self.assertFalse(worktree.exists())
        self.assertEqual(self.anchored(), cleared.proven[0].sha)


class StandingAnchorTest(_ReclaimTestCase):
    """A note this host is still pinning is a surface of its own.

    An anchor outlives the checkout it was taken from, so an answer about the
    checkout says nothing about it: a pass that found the tree already gone
    would otherwise report the issue settled while this host went on being the
    only name a commit has.
    """

    def repointing(self, spec, issue_number: int) -> str:
        """Read the anchor, then move it where a racer would."""
        ref = obligations._anchor_ref(spec, issue_number)
        anchored = obligations._note_at(spec, ref)
        if anchored:
            self.repointed = self.world.commit_on(
                self.clone, f"{self.branch}{RACED_BRANCH}",
            )
            _run_git(_UPDATE_REF, ref, self.repointed, cwd=self.clone)
        return anchored

    def test_a_note_outliving_its_checkout_is_named(self) -> None:
        # The checkout came down and the note over it did not, so the pass
        # after has no checkout left to find the issue by -- and would report
        # nothing at all left to do while the commit that note pins is one
        # nothing else on this host names.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)

        with patch.object(obligations, _ANCHOR_READ_SEAM, self.repointing):
            first = self.spend(cleared)
        again = self.spend(cleared)

        self.assertEqual(
            self.outcomes(first), _checkout_surface(FAILED, FAILED),
        )
        self.assertEqual(
            self.outcomes(again), _checkout_surface(ABSENT, FAILED),
        )
        self.assertFalse(again.settled)
        self.assertFalse(worktree.exists())
        self.assertEqual(self.anchored(), self.repointed)


class AsideRoomTest(_ReclaimTestCase):
    """What the room a checkout is moved aside inside is read for.

    A name is made there before anything is moved onto it, and the reading
    that finds one is what a pass killed mid-move is put right by -- so what
    that reading answers, and what it makes of a name nothing was moved onto,
    decides whether this issue is ever reclaimable again.
    """

    def reserved(self, worktree: Path) -> Path:
        """One name a move that never happened left standing in that room."""
        aside = worktree.parent / _ASIDE_RESERVED.format(ISSUE_NUMBER)
        aside.mkdir()
        return aside

    def test_a_reservation_nothing_moved_onto_goes(self) -> None:
        # A checkout carries its own `.git` at the very least, so an empty
        # room is a name a rename never happened onto rather than a tree moved
        # aside. Left standing, every later pass would read it as one and
        # refuse over a checkout that never went anywhere.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        aside = self.reserved(worktree)

        reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(CLEANED))
        self.assertFalse(aside.exists())
        self.assertFalse(worktree.exists())

    def test_a_room_that_would_not_be_read_keeps_it(self) -> None:
        # A room this pass could not read is not a room with nothing in it,
        # and spending the second answer on the first is how a checkout an
        # earlier pass left aside is passed over while this one takes another
        # down -- or reported absent over a tree nothing could see.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)

        with patch.object(reclamation, _ASIDE_SEAM, return_value=None):
            reclaimed = self.spend(cleared)

        self.assertEqual(self.outcomes(reclaimed), _checkout_surface(FAILED))
        self.assertTrue(worktree.is_dir())


class RepeatedPassTest(_ReclaimTestCase):
    """A teardown that stopped halfway is finished by the pass after it.

    Or refused by it, where finishing would take what the earlier one kept.
    """

    def stopping(self, *args: str, **options):
        """Run every git call but the removal, which stops the pass dead.

        Stands in for the process that did not come back: the note is written,
        the removal never happens, and what is on disk afterwards is what a
        crash between the two leaves.
        """
        if " ".join(args[:2]) == _WORKTREE_REMOVE:
            raise RuntimeError("the pass stopped here")
        return self.hardened(*args, **options)

    def test_an_anchor_from_an_earlier_pass_is_kept(self) -> None:
        # An earlier teardown left an anchor standing because what it pinned
        # was not what anybody had cleared, and the checkout has since been
        # made again. That ref is the only thing naming its commit, so a pass
        # that wrote over it would take it. The removal is refused instead, on
        # this pass and on every one after it.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        stranded = self.world.commit_on(
            self.clone, f"{self.branch}{STRANDED_BRANCH}",
        )
        _ran_git(
            self.clone,
            _UPDATE_REF,
            obligations._anchor_ref(self.spec, ISSUE_NUMBER),
            stranded,
        )

        kept = self.spend(cleared)
        again = self.spend(cleared)

        self.assertEqual(
            self.outcomes(kept), _checkout_surface(FAILED, FAILED),
        )
        self.assertEqual(
            self.outcomes(again), _checkout_surface(FAILED, FAILED),
        )
        self.assertTrue(worktree.is_dir())
        self.assertEqual(self.anchored(), stranded)

    def test_an_anchor_a_stopped_pass_left_is_spent(self) -> None:
        # A note is created and never overwritten, which is what keeps a
        # commit an earlier pass could not account for -- and what a pass that
        # stopped between the note and the removal leaves behind over a
        # checkout it had already moved out of reach of its own name. The pass
        # after it puts that checkout back where the scan reads it from, and
        # reads what the note pins: the commit its own verdict clears is one
        # nothing else has to hold, so the note is spent and taken again
        # rather than refusing this issue forever.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.hardened = commands._git_hardened

        with patch.object(commands, _HARDENED_SEAM, self.stopping):
            stopped = self.spend(cleared)

        self.assertEqual(
            self.outcomes(stopped), _checkout_surface(FAILED, FAILED),
        )
        self.assertFalse(worktree.exists())
        self.assertEqual(len(_left_aside(worktree)), 1)
        self.assertEqual(self.anchored(), cleared.proven[0].sha)

        finished = self.spend(cleared)

        self.assertEqual(self.outcomes(finished), _checkout_surface(CLEANED))
        self.assertFalse(worktree.exists())
        self.assertEqual(self.anchored(), "")

    def test_an_anchor_that_will_not_go_stops_it(self) -> None:
        # A note nobody could take away is one the write after it would be
        # refused by, so the removal does not run under it. The checkout stays
        # where it is and the pass after this one settles the note first.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.hardened = commands._git_hardened

        with patch.object(commands, _HARDENED_SEAM, self.stopping):
            self.spend(cleared)

        with patch.object(
            obligations, "_discard_anchor", return_value=False,
        ):
            kept = self.spend(cleared)

        self.assertEqual(
            self.outcomes(kept), _checkout_surface(FAILED, FAILED),
        )
        self.assertTrue(worktree.is_dir())


if __name__ == "__main__":
    unittest.main()
