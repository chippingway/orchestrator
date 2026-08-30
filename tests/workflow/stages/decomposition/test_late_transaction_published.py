# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A split whose candidate was measured on a pull request that already exists.

The transaction closes the pull request this cycle's work is on, hands the
issue to `umbrella`, activates the children, and reclaims the branch. Which
pull request that is depends on the side of publication the generation was
entered on -- a held plan one before the first push, the implementation one
past it -- and the second is the sharper of the two: left unsuperseded it is
an open change carrying work nobody will finish, pointing at a branch the
reclamation has already deleted.

So it is proved before it is closed, and the proof is the settlement's own.
A pull request nothing could read, one a human settled while the adjudication
was open, and one somebody pushed to are each a refusal with a durable retry
rather than a supersession taken on evidence that has been overtaken.
"""
from __future__ import annotations

import unittest

from orchestrator.workflow.stages.decomposition import (
    late_transaction as _late_transaction,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    _LateDisposition,
)
from orchestrator.workflow.state import WorkflowLabel

from tests.workflow.stages.decomposition.late_crash_support import (
    killed_after,
    refusing,
)
from tests.workflow.stages.decomposition.late_test_support import (
    CANDIDATE_SHA,
    KEYS,
    LATE_ISSUE_NUMBER,
    PUBLISHED_PR_NUMBER,
)
from tests.workflow.stages.decomposition.late_published_split_support import (
    PublishedSplitCase,
)
from tests.workflow.stages.decomposition.late_transaction_support import (
    CHILDREN,
    ERROR,
    KEY_PR_NUMBER,
    KEY_RESOURCES,
    SNAPSHOT_REF,
    SUPERSESSION_MARKER,
    first_child,
    label_of,
)

# A head somebody else pushed to the publication while the adjudication was
# open, so what the verdict was taken over is not what the branch carries now.
MOVED_HEAD = "cafef00d" * 5

STATE_CLOSED = "closed"
STATE_RECONCILED = "reconciled"
RESOURCE_PLAN_PR = "plan_pr"
GET_PR = "get_pr"
# The step a crash lands past on this road: the close is made and its
# obligation recorded, and the retirement behind it never runs.
SUPERSEDED = "_superseded"


class PublishedSupersessionTest(PublishedSplitCase, unittest.TestCase):
    """The publication is told where the work went, and closed."""

    def test_it_closes_the_publication(self) -> None:
        # Without this the transaction clears `pr_number`, lets the children
        # loose, and deletes the branch, leaving an open pull request carrying
        # superseded work with nothing on it saying so.
        self._transact(generation=self.generation)

        self.assertEqual(self.published_pr.state, STATE_CLOSED)
        self.assertIn(
            SUPERSESSION_MARKER, self.github.posted_pr_comments[-1][1],
        )

    def test_the_notice_links_forward_to_everything(self) -> None:
        self._transact(generation=self.generation)

        notice = self.github.posted_pr_comments[-1][1]
        self.assertIn(f"#{LATE_ISSUE_NUMBER}", notice)
        self.assertIn(SNAPSHOT_REF, notice)
        self.assertIn(CANDIDATE_SHA, notice)

    def test_it_records_the_obligation_settled(self) -> None:
        # The ledger is what holds the umbrella's terminal open until the
        # remote has let go, so a supersession that landed has to say so.
        self._transact(generation=self.generation)

        self.assertIn(
            [RESOURCE_PLAN_PR, str(PUBLISHED_PR_NUMBER), STATE_RECONCILED],
            [
                [entry["kind"], entry["target"], entry["state"]]
                for entry in self._pinned().get(KEY_RESOURCES) or []
            ],
        )

    def test_it_hands_the_issue_on_behind_the_close(self) -> None:
        # And the tail runs only once the pull request is settled: the label,
        # the cleared pointer, and the children.
        self._transact(generation=self.generation)

        self.assertEqual(
            label_of(self.github, LATE_ISSUE_NUMBER), WorkflowLabel.UMBRELLA,
        )
        self.assertIsNone(self._pinned().get(KEY_PR_NUMBER))


class PublishedSupersessionRefusalTest(
    PublishedSplitCase, unittest.TestCase,
):
    """Every reading that says this is not the publication that was judged."""

    def test_a_moved_publication_parks(self) -> None:
        # Somebody pushed to it while the adjudication was open, so the change
        # this verdict was about is not the change closing it would close.
        self.published_pr.head.sha = MOVED_HEAD

        with self.assertLogs(level=ERROR):
            outcome = self._transact(generation=self.generation)

        self._assert_left_alone(outcome)

    def test_a_settled_publication_parks(self) -> None:
        # A human merged or closed it themselves. Letting the children loose
        # beside a merge would hand the work to N issues after it landed.
        for merged in (True, False):
            with self.subTest(merged=merged):
                self.setUp()
                self.published_pr.merged = merged
                self.published_pr.state = STATE_CLOSED

                with self.assertLogs(level=ERROR):
                    outcome = self._transact(generation=self.generation)

                self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
                self.assertEqual(self.published_pr.merged, merged)

    def test_an_unreadable_publication_parks(self) -> None:
        # A fetched pull request is lazy, so the request that fails is as
        # likely to be the read as the write behind it -- and by then the
        # children are already live.
        with refusing(self.github, GET_PR):
            with self.assertLogs(level=ERROR):
                outcome = self._transact(generation=self.generation)

        self._assert_left_alone(outcome)

    def test_a_refused_supersession_parks(self) -> None:
        # The proof passed and the close itself did not land.
        self.github.unsupersedable_prs.add(PUBLISHED_PR_NUMBER)

        outcome = self._transact(generation=self.generation)

        self._assert_left_alone(outcome)

    def test_the_retry_supersedes_it(self) -> None:
        # The children are durable by then, so the retry is a read and a
        # close: the same recorded verdict settles once the disagreement is
        # reconciled, and the thread carries one notice.
        self.github.unsupersedable_prs.add(PUBLISHED_PR_NUMBER)
        self._transact(generation=self.generation)
        self.github.unsupersedable_prs.clear()

        self._resume()

        self.assertEqual(self.published_pr.state, STATE_CLOSED)
        self.assertEqual(
            len([
                body for _, body in self.github.posted_pr_comments
                if SUPERSESSION_MARKER in body
            ]),
            1,
        )
        self.assertEqual(len(self.github.created_child_issues), len(CHILDREN))

    def _assert_left_alone(self, outcome) -> None:
        """Parked with the publication open and no child let loose."""
        self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
        self.assertEqual(
            self._pinned().get(KEYS.park_reason),
            _late_transaction._late_outcome.PARK_SUPERSESSION_FAILED,
        )
        self.assertEqual(
            label_of(self.github, LATE_ISSUE_NUMBER),
            WorkflowLabel.DECOMPOSING,
        )
        self.assertEqual(
            first_child(self.github).labels[0].name, WorkflowLabel.BLOCKED,
        )
        self.assertEqual(self._pinned().get(KEY_PR_NUMBER), PUBLISHED_PR_NUMBER)


class PublishedSupersessionRetryTest(PublishedSplitCase, unittest.TestCase):
    """The window the retirement behind the supersession leaves open.

    The close is not the last step: the label, the cleared pointer, the
    children, and the branch all come after it. A tick that died in between
    comes back to a pull request it closed ITSELF, which reads exactly as a
    human's settlement does -- and the receipt on the thread is the only thing
    that tells the two apart.

    What the receipt buys is the STATE and nothing else. The branch is live
    for the whole of that window, so the head is proved on this path exactly
    as on the open one.
    """

    def test_a_death_past_the_close_resumes(self) -> None:
        # The window the supersession opens on this road: the pull request is
        # closed and its obligation reconciled, and the retirement behind them
        # never ran -- so the record is still live and the next tick reads a
        # publication it closed ITSELF. Told from a human's settlement only by
        # the receipt on the thread, and read as one it parks for good with
        # the children blocked behind a supersession already made.
        self._crash_past_the_close()
        self.assertEqual(self.published_pr.state, STATE_CLOSED)

        resumed = self._resume()

        self.assertEqual(resumed.disposition, _LateDisposition.SETTLED)
        self.assertEqual(
            label_of(self.github, LATE_ISSUE_NUMBER), WorkflowLabel.UMBRELLA,
        )
        self.assertNotEqual(
            first_child(self.github).labels[0].name, WorkflowLabel.BLOCKED,
        )
        # And it finishes as a READ: the notice is already on the thread and
        # the pull request is already closed, so it adds neither.
        self.assertEqual(
            len([
                body for _, body in self.github.posted_pr_comments
                if SUPERSESSION_MARKER in body
            ]),
            1,
        )

    def test_a_merged_publication_parks_past_it(self) -> None:
        # The receipt is not a licence. A human who reopened the pull request
        # and landed the work decided the opposite of what the supersession
        # claims, and handing it to children afterwards is the one outcome
        # nothing takes back.
        self._crash_past_the_close()
        self.published_pr.merged = True

        with self.assertLogs(level=ERROR):
            resumed = self._resume()

        self.assertEqual(resumed.disposition, _LateDisposition.PARKED)
        self.assertEqual(
            label_of(self.github, LATE_ISSUE_NUMBER),
            WorkflowLabel.DECOMPOSING,
        )

    def test_a_push_past_the_close_parks(self) -> None:
        # The receipt is not a licence one field over either. It says the
        # close was made and nothing about the branch behind it standing
        # still: a close does not freeze a ref, so somebody can push between
        # the crash and the retry. Waved through on the receipt alone, the
        # retry would settle the split, activate the children, and RECLAIM
        # that branch -- deleting a commit the snapshot, taken at the frozen
        # head, does not hold.
        self._crash_past_the_close()
        self.published_pr.head.sha = MOVED_HEAD

        with self.assertLogs(level=ERROR):
            resumed = self._resume()

        self.assertEqual(resumed.disposition, _LateDisposition.PARKED)
        self.assertEqual(
            label_of(self.github, LATE_ISSUE_NUMBER),
            WorkflowLabel.DECOMPOSING,
        )
        self.assertEqual(
            first_child(self.github).labels[0].name, WorkflowLabel.BLOCKED,
        )
        self.assertEqual(self.github.deleted_remote_branches, [])
        self.assertFalse(self.teardown.attempted)

    def test_the_park_names_the_push_not_a_write(self) -> None:
        # The supersession did not fail here -- this transaction made it --
        # so the notice that says "could not be superseded" would send the
        # human looking for a write that never went wrong. What they have to
        # reconcile is the head.
        self._crash_past_the_close()
        self.published_pr.head.sha = MOVED_HEAD

        with self.assertLogs(level=ERROR):
            self._resume()

        parked = self.github.posted_comments[-1][1]
        self.assertEqual(
            self._pinned().get(KEYS.park_reason),
            _late_transaction._late_outcome.PARK_SUPERSESSION_FAILED,
        )
        self.assertIn(MOVED_HEAD, parked)
        self.assertNotIn("could not be superseded", parked)

    def _crash_past_the_close(self) -> None:
        """The window itself: the close lands and the retirement never runs."""
        with self.assertRaises(KeyboardInterrupt):
            self._transact(
                generation=self.generation,
                killed=killed_after(_late_transaction, SUPERSEDED),
            )


if __name__ == "__main__":
    unittest.main()
