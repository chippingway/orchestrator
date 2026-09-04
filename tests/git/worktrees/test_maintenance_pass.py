# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one maintenance pass takes, what it refuses, and what it leaves behind.

The mutations are run for real: `worktree remove` against a tree on disk, a
leased delete against a bare repository, and a pinned `update-ref` against the
clone's own ref store. That is the whole point of the cases below -- what makes
this pass safe is that git and the remote refuse it when the world has moved,
and a fixture standing in for either would assert the pass's own reading back
at it.

What is asserted after a pass is the state of the host and the remote rather
than the calls it made, since that is what an operator is left with. The one
exception is the pair of failure cases, where a step that would not run is
installed on the owner that defines it: neither a bare repository nor a local
ref store can be made to turn a valid deletion down.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git.worktrees import maintenance, reclaim
from orchestrator.git.worktrees.models import (
    MaintenanceOutcome,
    MaintenanceReason,
    ProbeAnswer,
    ProvenTip,
    RetentionReason,
)
from tests.git.worktrees.artifact_test_support import (
    WIDGET_SLUG,
    _legacy_branch,
)
from tests.git.worktrees.candidate_host_test_support import (
    _branch_at,
    _track_file,
)
from tests.git.worktrees.eligibility_test_support import (
    ISSUE_NUMBER,
    OPEN_PR_STATE,
    _github,
    _pull_request,
    _terminal_issue,
)
from tests.git.worktrees.maintenance_test_support import (
    _always_claimed,
    _MaintenanceTestCase,
    _refused_delete,
    _unanswerable_claim,
)

PR_NUMBER = 42
WARNING = "WARNING"
INFO_LEVEL = "INFO"
LOOSE_FILE = "left-behind.txt"
LOOSE_CONTENT = "an agent's unfinished work\n"
IGNORE_FILE = ".gitignore"
HIDDEN_FILE = "secrets.env"
HIDDEN_CONTENT = "TOKEN=an operator's own\n"
IMPLEMENTING_LABEL = "workflow:implementing"
OBJECT_ID_LENGTH = 40
# A commit no artifact of this issue is standing on: what a proof taken a
# moment before the mutation is worth once somebody has pushed.
OTHER_SHA = "b" * OBJECT_ID_LENGTH


class OrderedCleanupTest(_MaintenanceTestCase):
    """A cleared candidate loses its checkout, its remote branch, and its ref."""

    def test_every_artifact_of_a_cleared_one_goes(self) -> None:
        self.landed()
        worktree = self.settled_checkout()

        swept = self.only_result()

        self.assertEqual(swept.outcome, MaintenanceOutcome.CLEANED)
        self.assertEqual(swept.reason, MaintenanceReason.RECLAIMED)
        self.assertFalse(worktree.exists())
        self.assertEqual(self.local_branches(), ())
        self.assertEqual(self.remote_branches(), ())

    def test_a_branch_only_one_loses_both_copies(self) -> None:
        self.landed()

        swept = self.only_result()

        self.assertEqual(swept.outcome, MaintenanceOutcome.CLEANED)
        self.assertEqual(self.local_branches(), ())
        self.assertEqual(self.remote_branches(), ())

    def test_a_remote_only_one_loses_its_copy(self) -> None:
        # Nothing local proved it and nothing local is deleted: the branch is
        # found by the remote listing and cleared through the remote's own tip.
        self.landed()
        _branch_at(self.clone, self.branch, None)

        swept = self.only_result()

        self.assertEqual(swept.outcome, MaintenanceOutcome.CLEANED)
        self.assertEqual(self.remote_branches(), ())

    def test_a_pass_writes_nothing_to_the_issue(self) -> None:
        # The artifacts are the whole of what this pass owns: an issue that has
        # ended keeps every record of how it ended.
        self.landed()
        self.settled_checkout()

        self.only_result()

        self.assertEqual(self.gh.posted_comments, [])
        self.assertEqual(self.gh.label_history, [])
        self.assertEqual(self.gh.write_state_calls, 0)


class GuardedCandidateTest(_MaintenanceTestCase):
    """Everything in front of the mutation keeps the artifacts where they are."""

    def setUp(self) -> None:
        super().setUp()
        self.landed()
        self.worktree = self.settled_checkout()

    def assert_untouched(self, swept) -> None:
        """The candidate is kept, and every artifact is still where it was."""
        self.assertEqual(swept.outcome, MaintenanceOutcome.RETAINED)
        self.assertTrue(self.worktree.exists())
        self.assertEqual(self.local_branches(), self.only_branch)
        self.assertEqual(self.remote_branches(), self.only_branch)

    def test_an_issue_being_run_is_left_alone(self) -> None:
        swept = self.only_result(claimed=_always_claimed)

        self.assert_untouched(swept)
        self.assertEqual(swept.reason, MaintenanceReason.ACTIVE_CLAIM)
        self.assertEqual(swept.subject, f"#{ISSUE_NUMBER}")

    def test_a_guard_that_raises_is_read_as_a_claim(self) -> None:
        with self.assertLogs(maintenance.log.name, level=WARNING):
            swept = self.only_result(claimed=_unanswerable_claim)

        self.assert_untouched(swept)
        self.assertEqual(swept.reason, MaintenanceReason.CLAIM_UNREADABLE)

    def test_a_checkout_touched_lately_is_left_alone(self) -> None:
        # The tree is clean and the classification clears it; what keeps it is
        # that somebody was in it moments ago.
        (self.worktree / LOOSE_FILE).write_text(LOOSE_CONTENT)
        (self.worktree / LOOSE_FILE).unlink()

        swept = self.only_result()

        self.assert_untouched(swept)
        self.assertEqual(swept.reason, MaintenanceReason.RECENT_ACTIVITY)

    def test_an_untimeable_checkout_is_left_alone(self) -> None:
        # The last gate fails closed like every one before it: a tree nobody
        # could time is not one to delete on the strength of the reads that
        # did answer.
        with patch.object(
            maintenance.evidence,
            "_quiet_checkout",
            return_value=ProbeAnswer.UNREADABLE,
        ):
            swept = self.only_result()

        self.assert_untouched(swept)
        self.assertEqual(swept.reason, MaintenanceReason.ACTIVITY_UNREADABLE)


class RetainedByClassificationTest(_MaintenanceTestCase):
    """A candidate the classification keeps is reported with its own reasons."""

    def assert_kept_for(self, swept, reason: RetentionReason) -> None:
        """The pass reports the classification's answer, in its vocabulary."""
        self.assertEqual(swept.outcome, MaintenanceOutcome.RETAINED)
        self.assertEqual(swept.reason, MaintenanceReason.UNPROVEN)
        self.assertEqual(
            tuple(kept.reason for kept in swept.retentions), (reason,),
        )
        self.assertEqual(swept.subject, swept.retentions[0].subject)

    def test_a_dirty_tree_keeps_the_whole_candidate(self) -> None:
        self.landed()
        worktree = self.settled_checkout()
        (worktree / LOOSE_FILE).write_text(LOOSE_CONTENT)

        swept = self.only_result()

        self.assert_kept_for(swept, RetentionReason.WORKTREE_DIRTY)
        self.assertTrue(worktree.exists())
        self.assertEqual(self.local_branches(), self.only_branch)

    def test_a_tree_hiding_files_keeps_it(self) -> None:
        # `worktree remove` would take these down without a word, which is why
        # the classification asks about them and the pass never gets a proof.
        _track_file(self.clone, IGNORE_FILE, f"{HIDDEN_FILE}\n")
        self.landed()
        worktree = self.settled_checkout()
        (worktree / HIDDEN_FILE).write_text(HIDDEN_CONTENT)

        with self.assertLogs(maintenance.log.name, level=INFO_LEVEL):
            swept = self.only_result()

        self.assert_kept_for(swept, RetentionReason.WORKTREE_IGNORED)
        self.assertTrue((worktree / HIDDEN_FILE).exists())

    def test_an_open_pull_request_keeps_the_branches(self) -> None:
        tip = self.landed()
        self.gh.existing_open_pr[self.branch] = _pull_request(
            PR_NUMBER, self.branch, tip, state=OPEN_PR_STATE,
        )

        swept = self.only_result()

        self.assert_kept_for(swept, RetentionReason.OPEN_PULL_REQUEST)
        self.assertEqual(self.remote_branches(), self.only_branch)

    def test_an_issue_that_has_not_ended_keeps_it(self) -> None:
        self.landed()
        self.gh = _github(_terminal_issue(
            closed=False, label_names=(IMPLEMENTING_LABEL,),
        ))

        swept = self.only_result()

        self.assert_kept_for(swept, RetentionReason.ISSUE_OPEN)
        self.assertEqual(self.local_branches(), self.only_branch)

    def test_an_unaccounted_commit_keeps_it(self) -> None:
        # Published, never merged, and no pull request carries it: the one copy
        # of that work is the branch this pass was asked about.
        self.published()

        swept = self.only_result()

        self.assert_kept_for(swept, RetentionReason.UNACCOUNTED_COMMITS)
        self.assertEqual(self.remote_branches(), self.only_branch)


class ExactTipTest(_MaintenanceTestCase):
    """Nothing is deleted that is not standing exactly where it was proved.

    The proof is handed to the teardown directly here, which is the only way to
    put a case between the classification and the mutation: in production the
    two are one call, and what separates them is a push or a commit landing in
    the microseconds between.
    """

    def reclaimed(self, *proven: ProvenTip):
        """Run the teardown over this host's candidate with a stated proof."""
        candidates = self.discovered()
        self.assertEqual(len(candidates), 1)
        return maintenance._reclaimed(candidates[0], proven)

    def test_a_branch_the_remote_has_moved_is_kept(self) -> None:
        self.landed()

        swept = self.reclaimed(ProvenTip(self.branch, OTHER_SHA))

        self.assertEqual(swept.outcome, MaintenanceOutcome.RETAINED)
        self.assertEqual(swept.reason, MaintenanceReason.TIP_MOVED)
        self.assertEqual(swept.subject, self.branch)
        self.assertEqual(self.remote_branches(), self.only_branch)
        self.assertEqual(self.local_branches(), self.only_branch)

    def test_a_moved_local_branch_survives(self) -> None:
        # The remote's copy is proved and goes; the local ref is standing on a
        # commit nobody cleared, so the pinned delete never runs.
        tip = self.landed()
        self.world.unpublish(self.clone, self.branch)
        moved = self.world.commit_on(
            self.clone, self.branch, start=self.branch,
        )

        swept = self.reclaimed(ProvenTip(self.branch, tip))

        self.assertNotEqual(moved, tip)
        self.assertEqual(swept.reason, MaintenanceReason.TIP_MOVED)
        self.assertEqual(self.local_branches(), self.only_branch)

    def test_a_checkout_that_moved_is_kept(self) -> None:
        # A worktree holds its HEAD and its own reflog, so removing it takes
        # whatever that HEAD names -- and an agent that committed since the
        # proof has moved it to something nobody cleared.
        self.landed()
        worktree = self.settled_checkout()

        swept = self.reclaimed(
            ProvenTip(str(worktree), OTHER_SHA),
            ProvenTip(self.branch, OTHER_SHA),
        )

        self.assertEqual(swept.reason, MaintenanceReason.TIP_MOVED)
        self.assertEqual(swept.subject, str(worktree))
        self.assertTrue(worktree.exists())
        self.assertEqual(self.remote_branches(), self.only_branch)

    def test_a_checkout_with_no_proof_is_kept(self) -> None:
        self.landed()
        worktree = self.settled_checkout()

        swept = self.reclaimed(ProvenTip(self.branch, OTHER_SHA))

        self.assertEqual(swept.reason, MaintenanceReason.TIP_UNREADABLE)
        self.assertTrue(worktree.exists())

    def test_a_branch_no_proof_names_is_passed_over(self) -> None:
        # A branch that has gone from both hosts since the scan named it: there
        # is nothing to delete, and nothing was cleared to delete it with.
        self.landed()

        swept = self.reclaimed()

        self.assertEqual(swept.outcome, MaintenanceOutcome.CLEANED)
        self.assertEqual(self.remote_branches(), self.only_branch)
        self.assertEqual(self.local_branches(), self.only_branch)


class RefusedStepTest(_MaintenanceTestCase):
    """A step that will not run stops the pass and leaves the rest discoverable."""

    def test_a_failed_remote_delete_keeps_the_ref(self) -> None:
        # The local ref is what the next discovery finds cheapest, so it is the
        # last thing to go -- and a remote delete that failed must not take it.
        self.landed()
        worktree = self.settled_checkout()

        with patch.object(
            reclaim, "_delete_remote_branch_at", side_effect=_refused_delete,
        ):
            swept = self.only_result()

        self.assertEqual(swept.outcome, MaintenanceOutcome.FAILED)
        self.assertEqual(swept.reason, MaintenanceReason.REMOTE_DELETE_FAILED)
        self.assertEqual(swept.subject, self.branch)
        self.assertFalse(worktree.exists())
        self.assertEqual(self.local_branches(), self.only_branch)
        self.assertEqual(self.remote_branches(), self.only_branch)

    def test_a_failure_leaves_it_discoverable(self) -> None:
        self.landed()
        self.settled_checkout()

        with patch.object(
            reclaim, "_delete_remote_branch_at", side_effect=_refused_delete,
        ):
            self.only_result()

        self.assertEqual(
            self.only_candidate().artifacts.branches, self.only_branch,
        )

    def test_a_second_pass_finishes_the_rest(self) -> None:
        self.landed()
        self.settled_checkout()

        with patch.object(
            reclaim, "_delete_remote_branch_at", side_effect=_refused_delete,
        ):
            self.only_result()
        swept = self.only_result()

        self.assertEqual(swept.outcome, MaintenanceOutcome.CLEANED)
        self.assertEqual(self.local_branches(), ())
        self.assertEqual(self.remote_branches(), ())

    def test_a_failed_local_delete_is_a_failure(self) -> None:
        self.landed()

        with patch.object(
            reclaim, "_delete_local_ref_at", side_effect=_refused_delete,
        ):
            swept = self.only_result()

        self.assertEqual(swept.outcome, MaintenanceOutcome.FAILED)
        self.assertEqual(swept.reason, MaintenanceReason.LOCAL_DELETE_FAILED)
        self.assertEqual(self.remote_branches(), ())
        self.assertEqual(self.local_branches(), self.only_branch)

    def test_a_checkout_that_stays_stops_the_pass(self) -> None:
        # Nothing past the checkout is touched, because a branch a worktree
        # still has checked out is one git will not let go of either.
        self.landed()
        worktree = self.settled_checkout()

        with patch.object(
            reclaim, "_remove_recognized_worktree", side_effect=_refused_delete,
        ):
            swept = self.only_result()

        self.assertEqual(swept.outcome, MaintenanceOutcome.FAILED)
        self.assertEqual(
            swept.reason, MaintenanceReason.WORKTREE_REMOVAL_FAILED,
        )
        self.assertEqual(swept.subject, str(worktree))
        self.assertEqual(self.remote_branches(), self.only_branch)
        self.assertEqual(self.local_branches(), self.only_branch)


class RepeatedPassTest(_MaintenanceTestCase):
    """Running the pass again costs nothing and takes nothing twice."""

    def test_a_cleared_host_offers_no_candidate(self) -> None:
        self.landed()
        worktree = self.settled_checkout()

        self.only_result()
        second = self.swept()

        self.assertEqual(second, ())
        self.assertFalse(worktree.exists())

    def test_a_half_finished_teardown_is_finished(self) -> None:
        # What carries an interrupted pass across a restart is the artifacts
        # themselves: nothing was written down, and the discovery finds what is
        # left of the candidate exactly as it found the whole of it.
        self.landed()
        worktree = self.settled_checkout()

        with patch.object(
            reclaim, "_delete_local_ref_at", side_effect=_refused_delete,
        ):
            self.only_result()
        swept = self.only_result()

        self.assertEqual(swept.outcome, MaintenanceOutcome.CLEANED)
        self.assertFalse(worktree.exists())
        self.assertEqual(self.local_branches(), ())
        self.assertEqual(self.remote_branches(), ())

    def test_both_layouts_go_in_one_pass(self) -> None:
        # One issue under two names, which is what a migration leaves: both
        # copies stand on the commit the base carries, and one pass takes all
        # four of them.
        legacy = _legacy_branch(ISSUE_NUMBER)
        tip = self.landed()
        _branch_at(self.clone, legacy, tip)
        self.world.publish(self.clone, legacy, tip)

        swept = self.only_result()

        self.assertEqual(swept.outcome, MaintenanceOutcome.CLEANED)
        self.assertEqual(self.local_branches(), ())
        self.assertEqual(self.remote_branches(), ())
        self.assertEqual(swept.candidate.artifacts.spec.slug, WIDGET_SLUG)


class OutcomeVocabularyTest(unittest.TestCase):
    """Every reason a pass can end on names exactly one outcome."""

    def test_every_reason_has_an_outcome(self) -> None:
        self.assertEqual(
            frozenset(maintenance._OUTCOMES),
            frozenset(MaintenanceReason),
        )


if __name__ == "__main__":
    unittest.main()
