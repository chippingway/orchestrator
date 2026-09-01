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
from tests.git.worktrees.candidate_host_test_support import _branch_at
from tests.git.worktrees.eligibility_test_support import (
    ISSUE_NUMBER,
    _candidate,
    _github,
    _terminal_issue,
)
from tests.git.worktrees.reclamation_test_support import (
    OTHER_ISSUE_NUMBER,
    _dirty,
    _holds,
    _lock_checkout,
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
            commands, "_git_hardened", self.hardened,
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


class StepFailureTest(_ReclaimTestCase):
    """A step that could not finish leaves everything behind it standing."""

    def test_a_checkout_git_will_not_remove_stays(self) -> None:
        # A locked worktree is a removal git refuses without `--force`, and
        # forcing is exactly what this teardown does not do.
        self.published()
        worktree = self.checkout()
        cleared = self.verdict(worktree=worktree, branches=self.branches)
        _lock_checkout(self.clone, worktree)

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
            "update-ref", f"refs/heads/{BASE_BRANCH}", tip, cwd=self.clone,
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

    def test_a_record_that_will_not_write_is_told(self) -> None:
        # The local copy is already gone, so there is nothing left to keep
        # back, and the ledger will not take the note that would have led a
        # later pass here. Nothing is deleted -- the remote is left exactly as
        # it was found -- and the pass says so where an operator reads it,
        # which is the only trace a host that will not write can keep.
        self.published()
        cleared = self.verdict()
        _branch_at(self.clone, self.branch)

        with patch.object(
            obligations, _RECORD_SEAM, return_value=False,
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


class ReconciliationTest(_ReclaimTestCase):
    """A teardown that stopped halfway is finished by the pass after it."""

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
