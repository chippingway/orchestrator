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
from orchestrator.git.worktrees import eligibility, evidence, inventory
from orchestrator.git.worktrees.models import (
    ArtifactSurface,
    ArtifactVerdict,
    BranchTip,
    ProbeAnswer,
    ProvenTip,
    SurfaceOutcome,
)

from tests.git.worktrees.artifact_test_support import (
    WIDGET_SLUG,
    _namespaced_branch,
)
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

# The transport seam both the refusing and the racing case stand in for.
_REMOTE_DELETE_SEAM = "_delete_remote_ref"


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
            head == _LOCAL_DELETE and args[2].startswith(_BRANCH_REFS)
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


class RefusedVerdictTest(_ReclaimTestCase):
    """A verdict that keeps its candidate is spent on nothing."""

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
