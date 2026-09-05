# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One oversized change, adjudicated once and reviewed twice, on a real repo.

The whole road an accepted candidate takes when the base moves under it, with
nothing about it seeded. A `workflow:validating` round publishes a change the
real counter reads past the ceiling, so the real size gate holds it and hands
the issue to the adjudication; the real adjudicator answers `single`, and the
settlement records the exemption and the digest of what that commit
contributes over the pair it froze. Then the base advances on the real remote
and the per-tick refresh replays the branch onto it and force-publishes the
result.

That replay is a commit no human ever saw, and everything here turns on it
being recognized as the change they already ruled on. The exemption and the
receipt move onto it, the push that put it there is leased to the head the
pull request was standing on, and the tick after it is the real
`workflow:validating` handler: the reviewer goes round again over the
rewritten checkout, approves, and the issue leaves for the documentation pass
-- with one measurement, one verdict, one trip through `workflow:decomposing`,
and two adjudication comments for the life of the issue, all of them naming
the commit a human was actually asked about.

Only three things are stood in for, and none of them is a decision: the two
agents' replies, the authenticated push, and the remote-side base freeze this
fixture has no token to take.
"""
from __future__ import annotations

import unittest

from orchestrator.workflow.late_split import (
    exemption as _exemption,
    rewrites as _rewrites,
)
from tests.git.base_sync.exemption_git_support import ISSUE, events_of
from tests.git.base_sync.journey_git_support import (
    OversizedJourneyRealGitFixture,
)
from tests.workflow.fixtures import (
    LABEL_DECOMPOSING,
    LABEL_DOCUMENTING,
    LABEL_VALIDATING,
)

EVENT_MEASUREMENT = "late_measurement"
EVENT_VERDICT = "late_verdict"
EVENT_REVIEW = "review_verdict"

VERDICT_FIELD = "verdict"
APPROVED = "approved"

# The two comments one adjudication puts on the issue thread: the notice that
# a push would take the pull request past the ceiling, and the verdict a human
# reached about it.
ADJUDICATION_COMMENTS = 2

KEY_PUBLISHED_SHA = "implementing_published_sha"
KEY_REVIEW_ROUND = "review_round"


class AdjudicatedRebaseJourneyTest(
    OversizedJourneyRealGitFixture, unittest.TestCase,
):
    """The change a human ruled on, carried through the base advance under it."""

    def setUp(self) -> None:
        super().setUp()
        self.accepted = self._commits_an_oversized_candidate()
        self.held = self._publishes_the_candidate(self.accepted)
        self.settled = self._accepted_as_single()
        self._advance_base(conflicting=False)
        self.pushed = self._refreshes()
        self.replayed = self._wt_head()

    def test_the_first_round_earned_the_exemption(self) -> None:
        # The premise, and it is a real reading rather than a seeded one: the
        # gate counted the diff past the ceiling, held the publication, and
        # the adjudicator's `single` is what put the verdict on the comment.
        self.assertTrue(self.held.held)
        self.assertEqual(len(events_of(self, EVENT_MEASUREMENT)), 1)
        self.assertEqual(len(events_of(self, EVENT_VERDICT)), 1)
        self.assertIn((ISSUE, LABEL_DECOMPOSING), self._gh.label_history)

    def test_the_rebase_is_leased_to_the_old_head(self) -> None:
        # The pull request was standing on the accepted commit, so that is
        # what the force-push is pinned against -- a branch somebody else
        # moved rejects it instead of being overwritten -- and what goes out
        # is the replay the gate proved rather than whatever HEAD became.
        self.assertNotEqual(self.replayed, self.accepted)
        self.assertEqual(self.pushed.revision, self.replayed)
        self.assertEqual(self.pushed.force_with_lease, self.accepted)

    def test_the_exemption_and_receipt_rotate(self) -> None:
        # The verdict moves on the write that receipts the landed push, so a
        # reader never sees an exemption for a commit no remote carries.
        durable = self._durable()
        self.assertTrue(_exemption.is_exempt(durable, self.replayed))
        identity = _exemption.read_semantic_identity(durable)
        self.assertEqual(identity.base_sha, self._merge_base())
        self.assertEqual(
            _rewrites.read_rewrite_authorization(durable).phase,
            _rewrites.LateRewritePhase.PUBLISHED,
        )
        self.assertEqual(durable.get(KEY_PUBLISHED_SHA), self.replayed)

    def test_the_reviewer_is_sent_back_to_the_replay(self) -> None:
        # The rebase is a new head to vote on, so the round the reviewer had
        # spent is reset and the issue goes back to them rather than on to a
        # merge gate that would pass on a SHA nobody read.
        self.assertIn((ISSUE, LABEL_VALIDATING), self._gh.label_history)
        self.assertEqual(self._durable().get(KEY_REVIEW_ROUND), 0)

    def test_the_reviewer_reruns_on_the_replay(self) -> None:
        # The real validating tick, over the checkout the refresh rewrote: one
        # reviewer round, one verdict, and the approval it earns carrying the
        # issue on to the documentation pass.
        reviewer = self._reviews()

        self.assertEqual(reviewer.call_count, 1)
        self.assertEqual(
            [record[VERDICT_FIELD] for record in events_of(self, EVENT_REVIEW)],
            [APPROVED],
        )
        self.assertIn((ISSUE, LABEL_DOCUMENTING), self._gh.label_history)

    def test_the_rerun_adjudicates_nothing_again(self) -> None:
        # The whole journey, counted once the reviewer has been round again:
        # one reading, one verdict, one trip through the adjudication, and the
        # two comments that trip posted -- both naming the commit a human was
        # actually asked about.
        self._reviews()

        self.assertEqual(len(events_of(self, EVENT_MEASUREMENT)), 1)
        self.assertEqual(len(events_of(self, EVENT_VERDICT)), 1)
        self.assertEqual(
            self._gh.label_history.count((ISSUE, LABEL_DECOMPOSING)), 1,
        )
        announced = self._issue_comments()
        self.assertEqual(len(announced), ADJUDICATION_COMMENTS)
        for body in announced:
            self.assertIn(self.accepted, body)

    def test_the_verdict_follows_the_work_it_covers(self) -> None:
        # Two rewrites separate the commit a human ruled on from the head the
        # approval leaves -- the base refresh's replay and the squash on
        # approval -- and the exemption is on the far side of both, so a later
        # reading of that head finds the change already decided.
        self._reviews()

        approved = self._wt_head()
        self.assertNotEqual(approved, self.accepted)
        self.assertTrue(_exemption.is_exempt(self._durable(), approved))


if __name__ == "__main__":
    unittest.main()
