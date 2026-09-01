# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a teardown takes down, what it refuses, and what it leaves findable.

Driven over a real clone, real checkouts, and a real bare remote, because
every claim here is about what git and that remote were left holding: a
checkout that is gone, a ref that is not, a branch the remote no longer
carries. The verdicts come from the classifier itself, so the proof each case
spends is the one production spends.

The failures are made rather than mocked wherever the host can make them -- a
locked worktree, a branch committed onto after the proof, a remote pushed past
it -- because what is under test is the refusal, and a refusal driven by a
stub of the reading it refuses on proves only that the stub was consulted.
"""

from __future__ import annotations

import contextlib
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.git import authentication, commands
from orchestrator.git.worktrees import (
    eligibility,
    evidence,
    inventory,
    obligations,
    reclamation,
)
from orchestrator.git.worktrees.models import (
    ArtifactSurface,
    ArtifactVerdict,
    BranchTip,
    ProbeAnswer,
    ProvenTip,
    SurfaceOutcome,
)
from tests.git.worktrees.artifact_test_support import (
    BASE_BRANCH,
    LIFECYCLE_LOGGER,
    WIDGET_SLUG,
    _namespaced_branch,
)
from tests.git.worktrees.candidate_host_test_support import (
    _branch_at,
    _track_file,
)
from tests.git.worktrees.eligibility_test_support import (
    ISSUE_NUMBER,
    _candidate,
    _github,
    _pull_request,
    _terminal_issue,
)
from tests.git.worktrees.reclamation_test_support import (
    OTHER_ISSUE_NUMBER,
    _dirty,
    _holds,
    _ran_git,
    _ReaddedCheckout,
    _ReclaimTestCase,
    _surfaces,
    _tip,
)
from tests.workflow.stages.question.question_real_git_test_support import (
    _run_git,
)

CLEANED = SurfaceOutcome.CLEANED
ABSENT = SurfaceOutcome.ABSENT
FAILED = SurfaceOutcome.FAILED

# The three destructive calls, in the spelling the recorder notes them by: the
# local two are the head of their argv, and the remote one is the transport
# call that carries the lease. The heads are matched whole, so the reads these
# steps take -- a `worktree list` under the same first word -- are not one of
# them, and the branch deletion is told from the record written either side of
# it by the ref it names.
_WORKTREE_REMOVE = "worktree remove"
_LOCAL_DELETE = "update-ref -d"
_REMOTE_DELETE = "push --delete"

_BRANCH_REFS = "refs/heads/"

# The transport seam both the refusing and the racing case stand in for, and
# the ledger seam the case about a host that will not write stands in for.
_REMOTE_DELETE_SEAM = "_delete_remote_ref"

_RECORD_SEAM = "_record_obligation"

# The write every note and every marker goes through, for the case about a
# host whose ref store takes nothing.
_NOTE_SEAM = "_written_note"

# The local git runner every case that stands in front of one patches.
_HARDENED_SEAM = "_git_hardened"

# The cleanliness read a case stands in front of, and the ref update the
# racers in these cases run.
_CLEAN_SEAM = "_clean_worktree"

_UPDATE_REF = "update-ref"

# Where a checkout is moved to for the case about a link left in its place.
MOVED_CHECKOUT = "moved-checkout"

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

# The branch a racer's commit is parked on, and the closed pull request that
# accounts for work no base will ever carry.
RACED_BRANCH = "-raced"

PR_NUMBER = 42


def _unstick(stuck: Path) -> None:
    """Give back the directory a case made unremovable, if it is still there.

    Suppressed rather than checked, because whether git got to it is the very
    thing the case is about: a removal that took the whole tree leaves nothing
    to hand back.
    """
    with contextlib.suppress(OSError):
        stuck.chmod(WRITABLE_DIR)


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
        _run_git("checkout", "-q", "--detach", cwd=worktree)
        _run_git(
            "commit", "-q", "--allow-empty", "-m", RACED_MESSAGE, cwd=worktree,
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
        self._clone = clone

    def __call__(self, *args, **options) -> ProbeAnswer:
        """Move the tree, point the registration at it, and link it back."""
        self.worktree.rename(self.elsewhere)
        _run_git("worktree", "repair", str(self.elsewhere), cwd=self._clone)
        self.worktree.symlink_to(self.elsewhere)
        return ProbeAnswer.CONFIRMED


class _DestructiveCalls:
    """The destructive calls a teardown makes, in the order it makes them.

    Recorded where each is made rather than inferred from what it left: a
    teardown that deleted the branch first and removed the checkout second
    leaves exactly the host a correctly ordered one leaves, so the order is
    only observable while it is running.

    A wrapper rather than a stub -- every call still runs -- because the order
    is being read off a teardown that has to reach its end for the reading to
    be about anything.
    """

    def __init__(self) -> None:
        self.taken: list[str] = []
        self._ran_git = commands._git_hardened
        self._deleted_remote = authentication._delete_remote_ref

    @contextlib.contextmanager
    def recording(self):
        """Watch both hosts for the duration of one teardown."""
        with patch.object(
            commands, _HARDENED_SEAM, self.hardened,
        ), patch.object(
            authentication, "_delete_remote_ref", self.remote_delete,
        ):
            yield

    def hardened(self, *args: str, **options):
        """One local git call, noted when it is one of the two that destroy."""
        head = " ".join(args[:2])
        if head == _WORKTREE_REMOVE or (
            head == _LOCAL_DELETE
            and any(named.startswith(_BRANCH_REFS) for named in args)
        ):
            self.taken.append(head)
        return self._ran_git(*args, **options)

    def remote_delete(self, *args, **options):
        """The lease-pinned deletion on the remote."""
        self.taken.append(_REMOTE_DELETE)
        return self._deleted_remote(*args, **options)


class WholeCandidateTest(_ReclaimTestCase):
    """A finished issue whose every artifact the verdict cleared."""

    def test_every_surface_of_a_finished_issue_goes(self) -> None:
        self.published()
        worktree = self.checkout()

        reclaimed = self.spend(
            self.verdict(worktree=worktree, branches=self.branches),
        )

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(CLEANED, CLEANED, CLEANED),
        )
        self.assertTrue(reclaimed.settled)
        self.assertEqual(self.standing(worktree), (False, False, False))

    def test_a_second_pass_finds_nothing_to_take(self) -> None:
        # Absent is success, which is what makes a teardown safe to re-run:
        # the same verdict spent again reports the artifacts as gone rather
        # than as three surfaces nobody could reclaim.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.spend(cleared)

        again = self.spend(cleared)

        self.assertEqual(
            self.outcomes(again), _surfaces(ABSENT, ABSENT, ABSENT),
        )
        self.assertTrue(again.settled)

    def dropped(self, artifacts, branch: str) -> bool:
        """Take the branch away where another actor would, standing on nothing.

        Installed in place of the live-checkout read, which is the last thing
        that runs before the deletion: the window between the reading that
        named the tip and the update that states it back.
        """
        _branch_at(self.clone, branch)
        return False

    def test_a_branch_taken_at_the_last_moment_goes(self) -> None:
        # Somebody else deletes the ref inside the window the stated old value
        # exists to close, so git refuses the update -- over a branch that is
        # not there rather than one that moved. Read as a failure it would
        # keep the issue in a report over an artifact nobody can find, and
        # nothing would ever settle it: the branch was what a later scan
        # would have found the candidate by.
        self.published()
        cleared = self.verdict()

        with patch.object(reclamation, "_checkouts_holding", self.dropped):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, CLEANED, ABSENT),
        )
        self.assertTrue(reclaimed.settled)

    def unpublished(self, *args, **options) -> bool:
        """Let another actor take the branch off the remote, then refuse.

        Installed in place of the leased deletion, which is where the window
        is: the remote was read a moment before, and the lease it carries is
        refused for a ref that has gone exactly as for one that has moved.
        """
        self.world.unpublish(self.clone, self.branch)
        return False

    def test_a_remote_taken_under_the_lease_goes(self) -> None:
        # Somebody else deletes the branch on the remote between the reading
        # and the push. The lease is refused over a ref that is not there,
        # which is the deletion this was for happening without it -- read as a
        # failure it would keep a record nobody owes and a branch nothing
        # needs.
        self.published()
        cleared = self.verdict()

        with patch.object(
            authentication, _REMOTE_DELETE_SEAM, self.unpublished,
        ):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, ABSENT, CLEANED),
        )
        self.assertTrue(reclaimed.settled)
        self.assertEqual(obligations._recorded_obligations(self.spec), ())

    def test_the_order_keeps_a_failure_findable(self) -> None:
        # The checkout before the branch it stands on, which is git's rule,
        # and the remote branch before the local one, which is this domain's:
        # the local artifacts are what a later scan finds the candidate by, so
        # they are the last thing a teardown may take.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        watched = _DestructiveCalls()

        with watched.recording():
            reclaimed = self.spend(cleared)

        self.assertTrue(reclaimed.settled)
        self.assertEqual(
            watched.taken, [_WORKTREE_REMOVE, _REMOTE_DELETE, _LOCAL_DELETE],
        )


class VerdictPermissionTest(_ReclaimTestCase):
    """What a verdict authorizes, and what it leaves exactly as it was."""

    def test_a_retained_candidate_is_left_alone(self) -> None:
        self.published()
        worktree = self.checkout()
        self.gh = _github(_terminal_issue(closed=False))

        reclaimed = self.spend(
            self.verdict(worktree=worktree, branches=self.branches),
        )

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(FAILED, FAILED, FAILED),
        )
        self.assertFalse(reclaimed.settled)
        self.assertEqual(self.standing(worktree), (True, True, True))

    def test_the_artifacts_are_not_read_at_all(self) -> None:
        # The verdict is the whole of the permission, so a candidate it keeps
        # costs no git process here: a second opinion taken at this point
        # could disagree with the one that already refused.
        self.published()
        self.gh = _github(_terminal_issue(closed=False))
        kept = self.verdict()

        with patch.object(evidence, "_local_branch_tip") as read:
            self.spend(kept)
            read.assert_not_called()

    def test_a_branch_nothing_cleared_is_left(self) -> None:
        # An eligible verdict that hands over no commit for a branch it names
        # authorizes nothing about it. There is no deletion to run and none to
        # write down: a record is the note that a deletion of one commit is
        # owed, and no commit was ever cleared here.
        self.published()
        proofless = ArtifactVerdict(
            _candidate(self.spec, ISSUE_NUMBER, branches=self.branches),
        )

        reclaimed = self.spend(proofless)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, FAILED, FAILED),
        )
        self.assertEqual(self.standing()[1:], (True, True))
        self.assertEqual(obligations._recorded_obligations(self.spec), ())

    def test_a_branch_gone_everywhere_settles(self) -> None:
        # The classification clears a commit for every branch it finds on
        # either host, so a verdict handing over none for one it names is one
        # that found it on neither. There is nothing to delete and nothing
        # left anywhere for a later pass to find, so refusing it would be a
        # failure nothing could ever settle.
        cleared = self.verdict()

        reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, ABSENT, ABSENT),
        )
        self.assertTrue(reclaimed.settled)

    def test_a_branch_back_on_the_remote_is_left(self) -> None:
        # The same verdict, and the branch published again after it was taken.
        # What is under that name now is work nobody adjudicated, so it is not
        # deleted -- and the local copy is gone as well, so what would lead a
        # later pass back to it is the reminder written in its place.
        cleared = self.verdict()
        self.world.publish(self.clone, self.branch, BASE_BRANCH)

        reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, FAILED, ABSENT),
        )
        self.assertTrue(self.standing()[2])
        self.assertEqual(
            tuple(
                owed.subject
                for owed in obligations._recorded_obligations(self.spec)
            ),
            self.branches,
        )


class ArtifactOwnershipTest(_ReclaimTestCase):
    """Nothing outside the names this issue publishes under is touched."""

    def test_a_branch_this_issue_never_had_is_kept(self) -> None:
        # The shape a shared clone can produce: an eligible verdict carrying
        # the branch of the issue beside this one. The names are re-derived
        # here rather than read off the verdict, so the teardown refuses it
        # whoever assembled the candidate.
        stranger = _namespaced_branch(WIDGET_SLUG, OTHER_ISSUE_NUMBER)
        cleared = ArtifactVerdict(
            _candidate(self.spec, ISSUE_NUMBER, branches=(stranger,)),
            proven=(ProvenTip(stranger, self.published(stranger)),),
        )

        reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, FAILED, FAILED),
        )
        self.assertTrue(_holds(self.spec, stranger))

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

        self.assertEqual(
            self.outcomes(reclaimed), ((ArtifactSurface.WORKTREE, FAILED),),
        )
        self.assertTrue(stranger.exists())

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
        _run_git("worktree", "repair", str(elsewhere), cwd=self.clone)
        worktree.symlink_to(elsewhere)
        cleared = self.verdict(worktree=worktree, branches=self.branches)

        self.assertIs(
            evidence._checkout_identity(self.spec, ISSUE_NUMBER, worktree),
            ProbeAnswer.CONFIRMED,
        )

        reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(FAILED, CLEANED, FAILED),
        )
        self.assertTrue(elsewhere.is_dir())
        self.assertTrue(worktree.is_symlink())


class DivergentWorkTest(_ReclaimTestCase):
    """Work made after the proof keeps the artifact holding it."""

    def test_a_commit_after_the_verdict_keeps_all(self) -> None:
        # The branch and the checkout on it are both standing on a commit
        # nothing cleared, so neither may go -- and the remote's copy stays
        # with them, since what would have released it is this branch still
        # being the one that was proven.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        made = self.world.commit_on(self.clone, self.branch, start=self.branch)

        reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(FAILED, FAILED, FAILED),
        )
        self.assertEqual(self.standing(worktree), (True, True, True))
        self.assertEqual(_tip(self.clone, self.branch), made)

    def test_a_tree_written_in_since_keeps_it(self) -> None:
        # The proof said this tree was carrying nothing loose. It is not
        # spent on the tree that is there now, and the branch stays standing
        # behind it -- which is what a later scan finds the checkout by.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        _dirty(worktree)

        reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(FAILED, CLEANED, FAILED),
        )
        self.assertEqual(self.standing(worktree)[:2], (True, True))

    def test_a_branch_that_moved_is_refused_by_git(self) -> None:
        # The reading is stale by the time the deletion runs, which is the
        # window every check-then-act leaves open. Naming the old value makes
        # git the one that refuses, so the commit made in that window is
        # still on the branch afterwards.
        self.published()
        cleared = self.verdict()
        made = self.world.commit_on(self.clone, self.branch, start=self.branch)
        stale = BranchTip(
            answer=ProbeAnswer.CONFIRMED, sha=cleared.proven[0].sha,
        )

        with patch.object(evidence, "_local_branch_tip", return_value=stale):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, CLEANED, FAILED),
        )
        self.assertEqual(_tip(self.clone, self.branch), made)


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
        self.raced = _ran_git(worktree, "checkout", "--detach") or _ran_git(
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

        with patch.object(obligations, "_anchor_checkout", self.racing):
            reclaimed = self.spend(cleared)

        self.assertNotEqual(self.raced, 0)
        self.assertNotEqual(self.moved, 0)
        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(CLEANED, CLEANED, CLEANED),
        )
        self.assertTrue(reclaimed.settled)
        self.assertEqual(cleared.proven[0].sha, tip)

    def test_a_commit_raced_into_the_window_is_kept(self) -> None:
        # The lock this teardown holds is this process's own, and the agent or
        # human writing in a checkout is neither. A commit made after every
        # reading and left on no branch is clean, so the removal that follows
        # takes it without complaint -- and the anchor written one process
        # before that removal is what keeps it, and what tells this pass that
        # what came down was not what anybody cleared.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        racer = _RacedCommit()

        with patch.object(evidence, _CLEAN_SEAM, racer):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(FAILED, CLEANED, FAILED),
        )
        self.assertFalse(worktree.exists())
        self.assertTrue(_holds(self.spec, self.branch))
        self.assertEqual(
            _tip(
                self.clone,
                obligations._anchor_ref(self.spec, ISSUE_NUMBER),
            ),
            racer.made,
        )


class StepFailureTest(_ReclaimTestCase):
    """A step that could not finish leaves everything behind it standing."""

    def test_a_checkout_git_will_not_remove_stays(self) -> None:
        # A locked worktree is a removal git refuses without `--force`, and
        # forcing is exactly what this teardown does not do.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        _ran_git(self.clone, "worktree", "lock", str(worktree))

        reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(FAILED, CLEANED, FAILED),
        )
        self.assertEqual(self.standing(worktree)[:2], (True, True))

    def test_a_symbolic_branch_keeps_what_it_names(self) -> None:
        # `update-ref` follows a symbolic ref, and every reading behind the
        # proof resolves through one: a branch pointed at the base reads as
        # standing on the base's own commit, passes, and takes `refs/heads/`
        # of that base with it while this issue's name is left dangling.
        # Nothing here makes such a branch, and nothing here deletes one.
        tip = self.published()
        cleared = self.verdict()
        _run_git(
            _UPDATE_REF, f"{_BRANCH_REFS}{BASE_BRANCH}", tip,
            cwd=self.clone,
        )
        _run_git(
            "symbolic-ref",
            f"refs/heads/{self.branch}",
            f"refs/heads/{BASE_BRANCH}",
            cwd=self.clone,
        )

        reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, CLEANED, FAILED),
        )
        self.assertEqual(_tip(self.clone, BASE_BRANCH), tip)

    def test_a_host_that_writes_nothing_is_told(self) -> None:
        # The local copy is already gone, so there is nothing left to keep
        # back, and this host will take no ref at all: not the note that would
        # have led a later pass here, and not the branch that would have had
        # the scan find the issue again. Nothing is deleted -- the remote is
        # left exactly as it was found -- and the pass says so where an
        # operator reads it, which is the only trace such a host can keep.
        self.published()
        cleared = self.verdict()
        _branch_at(self.clone, self.branch)

        with patch.object(
            obligations, _NOTE_SEAM, return_value=False,
        ), self.assertLogs(LIFECYCLE_LOGGER, "ERROR") as watched:
            reclaimed = self.spend(cleared)
            reported = watched.output

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, FAILED, ABSENT),
        )
        self.assertTrue(self.standing()[2])
        self.assertEqual(obligations._recorded_obligations(self.spec), ())
        self.assertTrue(
            any(self.branch in line for line in reported), msg=reported,
        )

    def test_a_remote_pushed_past_keeps_the_branch(self) -> None:
        # What the remote carries now is not the commit anybody cleared, and
        # the lease behind the deletion would refuse it even if this did not.
        self.published()
        cleared = self.verdict()
        ahead = f"{self.branch}-ahead"
        self.world.commit_on(self.clone, ahead, start=self.branch)
        self.world.publish(self.clone, self.branch, ahead)

        reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, FAILED, FAILED),
        )
        self.assertEqual(self.standing()[1:], (True, True))

    def test_a_checkout_added_mid_teardown_keeps_it(self) -> None:
        # The tree this issue's checkout was removed from is a tree anything
        # may be added back into, and `update-ref` deletes a branch out from
        # under a live checkout where `branch -D` refuses. So the worktrees
        # are asked again with the deletion: what the pass opened by reading
        # is not what is standing on the branch by the time it gets here.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)

        readded = _ReaddedCheckout(self.checkout)

        with patch.object(authentication, _REMOTE_DELETE_SEAM, readded):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(CLEANED, CLEANED, FAILED),
        )
        self.assertTrue(_holds(self.spec, self.branch))
        self.assertTrue(readded.loose.exists())

    def test_a_remote_that_will_not_answer_keeps_it(self) -> None:
        # An unasked question is not a branch the remote does not carry, and
        # only the second of those lets a deletion through.
        self.published()
        cleared = self.verdict()
        self.world.unreachable(self.spec)

        reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, FAILED, FAILED),
        )
        self.assertTrue(_holds(self.spec, self.branch))

    def test_a_failed_branch_read_stops_both(self) -> None:
        # Nothing was established about what this host holds, so nothing says
        # the branch is still the one that was cleared -- on either host.
        self.published()
        cleared = self.verdict()
        unread = BranchTip(answer=ProbeAnswer.UNREADABLE)

        with patch.object(evidence, "_local_branch_tip", return_value=unread):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, FAILED, FAILED),
        )
        self.assertEqual(self.standing()[1:], (True, True))


class LateChangeTest(_ReclaimTestCase):
    """What arrives, or goes, after the reading the step ahead of it ran on.

    Every case here is one window: between a probe and the destructive step it
    gates. The lock this pass holds is its own, git's own locks stop commits
    rather than writes, and the remote is asked over a network -- so each of
    those windows is one another hand can reach into, and what is under test
    is what this pass does when one of them did.
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

    def arriving(self, *args: str, **options):
        """Add a checkout on the branch just before the update that deletes it.

        The window the lock cannot cover, since it is this process's own and
        the `worktree add` a human or another process runs does not queue for
        it. Only the branch deletion is stood in front of: the notes this pass
        writes go through the same command under the same first two words.
        """
        head = " ".join(args[:2])
        if head == _LOCAL_DELETE and any(
            named.startswith(_BRANCH_REFS) for named in args
        ):
            self.arrived = self.world.attached_checkout(
                self.spec, ISSUE_NUMBER, self.branch,
            )
        return self.hardened(*args, **options)

    def losing(self, *args, **options) -> bool:
        """Take the local branch away while the remote is being asked."""
        _branch_at(self.clone, self.branch)
        return False

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

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(FAILED, CLEANED, FAILED),
        )
        self.assertEqual(hidden.read_text(), HIDDEN_CONTENT)
        self.assertTrue(_holds(self.spec, self.branch))

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

        with patch.object(obligations, "_anchor_checkout", self.hiding):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(FAILED, CLEANED, FAILED),
        )
        self.assertIs(
            evidence._clean_worktree(worktree), ProbeAnswer.CONFIRMED,
        )
        self.assertEqual(
            (worktree / HIDDEN_FILE).read_text(), HIDDEN_CONTENT,
        )

    def test_a_checkout_arriving_mid_delete_stays(self) -> None:
        # `update-ref` has no refusal for a branch some checkout is on, so the
        # one in front of it is a reading -- and a `worktree add` from outside
        # this process lands after it and leaves a tree whose HEAD names a ref
        # nothing resolves. Git reports that tree on the branch whatever
        # became of the ref, so the same question put again afterwards finds
        # it, and the deletion is undone.
        tip = self.published()
        cleared = self.verdict()
        self.hardened = commands._git_hardened

        with patch.object(commands, _HARDENED_SEAM, self.arriving):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, CLEANED, FAILED),
        )
        self.assertEqual(_tip(self.clone, self.branch), tip)
        self.assertEqual(_tip(self.arrived, "HEAD"), tip)

    def test_a_branch_taken_mid_push_is_absent(self) -> None:
        # The gate in front of the local deletion runs after the remote has
        # been asked, which takes as long as a network does. A branch somebody
        # deleted in that window is one this surface has to report as gone:
        # reported as one it refused, the issue would be kept in a report
        # forever over an artifact nobody can find. What carries the leftover
        # on the remote is the record the remote step wrote first.
        self.published()
        cleared = self.verdict()

        with patch.object(authentication, _REMOTE_DELETE_SEAM, self.losing):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, FAILED, ABSENT),
        )
        self.assertNotEqual(
            obligations._recorded_obligations(self.spec), (),
        )


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

    def removing(self, *args: str, **options):
        """Swap the tree away in the one window no reading can close.

        Installed in place of the local git runner and acting on the removal
        itself: what is left between the last reading and the command is the
        command's own argument, which the command resolves for itself.
        """
        if " ".join(args[:2]) == _WORKTREE_REMOVE:
            self.moved()
        return self.hardened(*args, **options)

    def test_a_tree_moved_before_the_read_is_kept(self) -> None:
        # The window the early type check leaves open: everything from that
        # check to the removal, which is where a rename, a repair, and a link
        # fit comfortably. Retaken one process before the removal, the reading
        # is about where the path leads rather than how it is spelled -- and a
        # link answers a directory this pass was never asked about.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        moved = self.swapping(worktree)

        with patch.object(evidence, _CLEAN_SEAM, moved):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed)[0], (ArtifactSurface.WORKTREE, FAILED),
        )
        self.assertTrue(moved.elsewhere.is_dir())
        self.assertTrue(worktree.is_symlink())

    def test_a_tree_moved_at_the_last_moment_is_told(self) -> None:
        # The window no reading can close, since the removal resolves its own
        # argument. What is left is not to lie about it: a path still standing
        # once the command came back clean is a path whose tree was not what
        # came down, and a surface reported cleaned over one would settle the
        # issue and leave whatever is there named by nothing.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.moved = self.swapping(worktree)
        self.hardened = commands._git_hardened

        with patch.object(commands, _HARDENED_SEAM, self.removing):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed)[0], (ArtifactSurface.WORKTREE, FAILED),
        )
        self.assertFalse(reclaimed.settled)
        self.assertTrue(worktree.is_symlink())


class AnchorReconciliationTest(_ReclaimTestCase):
    """What becomes of the commit a removal pinned, on this pass and after.

    An anchor outlives the checkout it was taken from, so the pass that
    settles one is never the pass that wrote it. These are the passes after:
    the removal that could not finish, the scan that has nothing left to
    report, and the ledger that goes on naming what this host is holding.
    """

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
        self.addCleanup(_unstick, stuck)
        return stuck

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

        with patch.object(obligations, "_anchored_commit", self.repointing):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed)[0], (ArtifactSurface.WORKTREE, FAILED),
        )
        self.assertEqual(
            _tip(self.clone, obligations._anchor_ref(self.spec, ISSUE_NUMBER)),
            self.repointed,
        )

    def test_a_rejected_issue_s_note_is_let_go(self) -> None:
        # Rejected work is never in any base -- that is what rejected means --
        # so an anchor an interrupted discard left over one would be measured
        # against the only test it can never pass, on this pass and on every
        # pass after it. What accounts for the commit is the pull request it
        # went out on, which is the same second proof the classification runs.
        tip = self.world.commit_on(self.clone, self.branch)
        self.world.publish(self.clone, self.branch, self.branch)
        self.gh.add_pr(_pull_request(PR_NUMBER, self.branch, tip))
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)

        with patch.object(
            obligations, "_discard_anchor", return_value=False,
        ):
            self.spend(cleared)

        self.assertEqual(
            _tip(self.clone, obligations._anchor_ref(self.spec, ISSUE_NUMBER)),
            tip,
        )

        swept = reclamation._reclaim_recorded_notes(self.gh, self.spec)

        self.assertEqual(
            tuple((taken.surface, taken.outcome) for taken in swept),
            ((ArtifactSurface.ANCHOR, CLEANED),),
        )
        self.assertEqual(
            obligations._anchored_commit(self.spec, ISSUE_NUMBER), "",
        )

    def test_a_failed_removal_keeps_what_it_pinned(self) -> None:
        # A non-zero result is not a checkout still standing. The command
        # deletes the tree and then deletes the administrative directory
        # beside it whatever the first half did, so by the time it reports
        # failure the HEAD and the reflog that held a raced commit are already
        # gone -- and the note is the only name that commit has left.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        self.stuck(worktree)
        racer = _RacedCommit()

        with patch.object(evidence, _CLEAN_SEAM, racer):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed)[0], (ArtifactSurface.WORKTREE, FAILED),
        )
        self.assertEqual(
            _tip(self.clone, obligations._anchor_ref(self.spec, ISSUE_NUMBER)),
            racer.made,
        )

    def test_a_note_outliving_its_artifacts_is_named(self) -> None:
        # The checkout came down and what it was standing on was not what
        # anybody cleared, so the note stays. The pass after takes the
        # branches -- there is no checkout left to hold them back -- and the
        # scan then reports nothing at all for this issue, which is the state
        # the ledger exists for: it goes on naming the commit this host is the
        # only name for, pass after pass, until somebody settles it.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        racer = _RacedCommit()

        with patch.object(evidence, _CLEAN_SEAM, racer):
            self.spend(cleared)

        for candidate in eligibility._classified_candidates(
            _github(), inventory._local_issue_inventory((self.spec,)).issues,
        ):
            self.spend(candidate)

        self.assertEqual(
            inventory._local_issue_inventory((self.spec,)).issues, (),
        )
        named = tuple(
            (taken.surface, taken.outcome)
            for taken in reclamation._reclaim_recorded_notes(
                self.gh, self.spec,
            ) + reclamation._reclaim_recorded_notes(self.gh, self.spec)
        )

        self.assertEqual(
            named, ((ArtifactSurface.ANCHOR, FAILED),) * 2,
        )
        self.assertEqual(
            _tip(self.clone, obligations._anchor_ref(self.spec, ISSUE_NUMBER)),
            racer.made,
        )

    def test_a_note_that_would_not_go_is_not_settled(self) -> None:
        # The checkout is gone and the note over it is not, which is a
        # teardown that has left something behind: reported settled, the
        # branch beside it would go on the next pass and the note would be
        # left with nothing naming it. What it holds is the commit that was
        # cleared, so the sweep afterwards finds the base carrying it and lets
        # it go.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)

        with patch.object(
            obligations, "_discard_anchor", return_value=False,
        ):
            reclaimed = self.spend(cleared)

        self.assertEqual(
            self.outcomes(reclaimed)[0], (ArtifactSurface.WORKTREE, FAILED),
        )
        self.assertFalse(reclaimed.settled)
        self.assertFalse(worktree.exists())

        swept = reclamation._reclaim_recorded_notes(self.gh, self.spec)

        self.assertEqual(
            tuple((taken.surface, taken.outcome) for taken in swept),
            ((ArtifactSurface.ANCHOR, CLEANED),),
        )
        self.assertEqual(
            obligations._anchored_commit(self.spec, ISSUE_NUMBER), "",
        )


class ReconciliationTest(_ReclaimTestCase):
    """A teardown that stopped halfway is finished by the pass after it.

    Or refused by it, where finishing would take what the earlier one kept.
    """

    def test_an_anchor_from_an_earlier_pass_is_kept(self) -> None:
        # An earlier teardown left an anchor standing because what it pinned
        # was not what anybody had cleared, and the checkout has since been
        # made again. That ref is the only thing naming its commit, so a pass
        # that wrote over it would take it -- and the pass after that would
        # discharge whatever it found. The removal is refused instead, on this
        # pass and on every one after it.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        stranded = self.world.commit_on(
            self.clone, f"{self.branch}-stranded",
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
            self.outcomes(kept)[0], (ArtifactSurface.WORKTREE, FAILED),
        )
        self.assertEqual(
            self.outcomes(again)[0], (ArtifactSurface.WORKTREE, FAILED),
        )
        self.assertTrue(worktree.exists())
        self.assertEqual(
            _tip(self.clone, obligations._anchor_ref(self.spec, ISSUE_NUMBER)),
            stranded,
        )

    def stopping(self, *args: str, **options):
        """Run every git call but the removal, which stops the pass dead.

        Stands in for the process that did not come back: the note is written,
        the removal never happens, and what is on disk afterwards is what a
        crash between the two leaves.
        """
        if " ".join(args[:2]) == _WORKTREE_REMOVE:
            raise RuntimeError("the pass stopped here")
        return self.hardened(*args, **options)

    def test_an_anchor_a_stopped_pass_left_is_spent(self) -> None:
        # A note is created and never overwritten, which is what keeps a
        # commit an earlier pass could not account for -- and what a pass that
        # stopped between the note and the removal leaves behind over a
        # checkout that is still standing. The pass after it reads what the
        # note pins: the commit its own verdict clears is one nothing else has
        # to hold, so the note is spent and taken again rather than refusing
        # this issue forever.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        anchor = obligations._anchor_ref(self.spec, ISSUE_NUMBER)
        self.hardened = commands._git_hardened

        with patch.object(commands, _HARDENED_SEAM, self.stopping):
            stopped = self.spend(cleared)

        self.assertEqual(
            self.outcomes(stopped)[0], (ArtifactSurface.WORKTREE, FAILED),
        )
        self.assertTrue(worktree.exists())
        self.assertEqual(_tip(self.clone, anchor), cleared.proven[0].sha)

        finished = self.spend(cleared)

        self.assertEqual(
            self.outcomes(finished), _surfaces(CLEANED, ABSENT, CLEANED),
        )
        self.assertFalse(worktree.exists())
        self.assertEqual(
            obligations._anchored_commit(self.spec, ISSUE_NUMBER), "",
        )

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
            self.outcomes(kept)[0], (ArtifactSurface.WORKTREE, FAILED),
        )
        self.assertTrue(worktree.exists())

    def test_a_branch_the_ledger_lost_comes_back(self) -> None:
        # The local copy went before the teardown reached it and the ledger
        # would not take a note for it, so nothing on this host would name the
        # leftover on the remote. What is left to write is a different ref:
        # the branch goes back where the scan reads its candidates from, at
        # the commit this verdict cleared -- so the pass after this one has a
        # candidate to find, proves it again, and finishes the deletion.
        tip = self.published()
        cleared = self.verdict()
        _branch_at(self.clone, self.branch)

        with patch.object(obligations, _RECORD_SEAM, return_value=False):
            stopped = self.spend(cleared)

        self.assertEqual(
            self.outcomes(stopped), _surfaces(None, FAILED, ABSENT),
        )
        self.assertEqual(obligations._recorded_obligations(self.spec), ())
        self.assertEqual(_tip(self.clone, self.branch), tip)

        for candidate in eligibility._classified_candidates(
            _github(), inventory._local_issue_inventory((self.spec,)).issues,
        ):
            self.spend(candidate)

        self.assertEqual(self.standing(), (False, False, False))

    def test_a_half_finished_teardown_is_found_again(self) -> None:
        # Nothing is carried between the two passes. The second rebuilds the
        # candidate from what is still on this host and classifies it against
        # a client of its own, which is all a restarted process would have --
        # and the artifacts the first pass would not take are what lead it
        # back to the remote branch nobody could delete.
        self.published()
        worktree = self.checkout()

        with patch.object(
            authentication, _REMOTE_DELETE_SEAM, return_value=False,
        ):
            first = self.spend(
                self.verdict(worktree=worktree, branches=self.branches),
            )

        self.assertEqual(
            self.outcomes(first), _surfaces(CLEANED, FAILED, FAILED),
        )
        self.assertEqual(self.standing(worktree), (False, True, True))

        scanned = inventory._local_issue_inventory((self.spec,))
        verdicts = eligibility._classified_candidates(
            _github(), scanned.issues,
        )
        second = self.spend(verdicts[0])

        self.assertEqual(
            self.outcomes(second), _surfaces(None, CLEANED, CLEANED),
        )
        self.assertEqual(self.standing(worktree), (False, False, False))
        self.assertEqual(
            inventory._local_issue_inventory((self.spec,)).issues, (),
        )


if __name__ == "__main__":
    unittest.main()
