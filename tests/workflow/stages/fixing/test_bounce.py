# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the no-feedback bounce does about a commit nobody published.

The validating route reaches that exit carrying an unanswered reviewer round:
the feedback that started it is a comment the orchestrator authored, so every
rescan filters it out and no later tick re-runs the dev on it. A commit an
earlier round left in the worktree -- a run whose outcome the live-pause guard
discarded, a run killed before its push -- therefore has to be published here
or the reviewer re-reads a head that is missing it.

The publish is only as bold as the probe it stands on, so each refusal that
probe makes is pinned beside it: the bounce still lands, unpushed, and the
commit waits for a round that can vouch for it.
"""

from __future__ import annotations

import unittest

from tests.workflow.stages.fixing import fixing_test_support as support

AHEAD_BEHIND = "branch_ahead_behind"
AUTHED_FETCH = support.AUTHED_FETCH
AUTHED_FETCH_RESULT = "authed_fetch_result"
DIRTY_FILES = "dirty_files"
ISSUE = support.ISSUE
MagicMock = support.MagicMock
PENDING_FIX_REVIEWER_COMMENT_ID = support.PENDING_FIX_REVIEWER_COMMENT_ID
PUSH_BRANCH = support.PUSH_BRANCH
REVIEW_ROUND = support.REVIEW_ROUND
RUN_AGENT = support.RUN_AGENT
TEMP_ROOT = support.TEMP_ROOT
VALIDATING = support.VALIDATING
_StrandedFixingFixtureMixin = support._StrandedFixingFixtureMixin

# The round the fixture seeds, and the one a published fix moves it to.
SEEDED_ROUND = 2
SPENT_ROUND = 3

# A checkout that is not on disk at all: a terminal cleanup ran, or the
# orchestrator moved host between the commit and this tick.
ABSENT_WORKTREE = TEMP_ROOT / "orchestrator-test-fixing-absent"

# What each probe refusal is seeded with, named by the shape it stands for.
UNVOUCHED_SHAPES = (
    ("no stranded commit", {AHEAD_BEHIND: (0, 0)}),
    ("dirty tree", {AHEAD_BEHIND: (1, 0), DIRTY_FILES: ("AGENTS.md",)}),
    ("remote moved", {AHEAD_BEHIND: (1, 2)}),
    (
        "fetch failed",
        {
            AHEAD_BEHIND: (1, 0),
            AUTHED_FETCH_RESULT: MagicMock(returncode=1, stderr="boom"),
        },
    ),
)


class NoFeedbackBounceTest(unittest.TestCase, _StrandedFixingFixtureMixin):

    def test_bounce_publishes_the_stranded_commit(self) -> None:
        # The clean worktree HEAD is strictly ahead of the remote PR branch --
        # the fix a dev run committed under a live `paused` and never got to
        # push. The bounce publishes it and counts the reviewer round it
        # spends, so the head the reviewer reads next tick carries the fix.
        gh, issue = self._seed_stranded_bounce()

        mocks = self._run_stranded_bounce(
            gh, issue, TEMP_ROOT, branch_ahead_behind=(1, 0),
        )

        # No agent ran: this tick republishes what an earlier one committed.
        mocks[RUN_AGENT].assert_not_called()
        mocks[PUSH_BRANCH].assert_called_once()
        self._assert_bounced(gh, round_n=SPENT_ROUND)

    def test_missing_worktree_bounces_unprobed(self) -> None:
        # Nothing on disk to publish from. The probe is left armed to prove
        # the handler gates on the checkout's existence before spending a
        # fetch on a path that is not there.
        gh, issue = self._seed_stranded_bounce()

        mocks = self._run_stranded_bounce(
            gh, issue, ABSENT_WORKTREE, branch_ahead_behind=(1, 0),
        )

        mocks[AUTHED_FETCH].assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()
        self._assert_bounced(gh, round_n=SEEDED_ROUND)

    def test_unvouched_shapes_bounce_without_pushing(self) -> None:
        for shape, run_options in UNVOUCHED_SHAPES:
            with self.subTest(shape=shape):
                gh, issue = self._seed_stranded_bounce()

                mocks = self._run_stranded_bounce(
                    gh, issue, TEMP_ROOT, **run_options,
                )

                mocks[PUSH_BRANCH].assert_not_called()
                self._assert_bounced(gh, round_n=SEEDED_ROUND)

    def test_failed_push_counts_no_round(self) -> None:
        # The push was attempted and refused, so the commit is still local:
        # counting the round would spend one on a head the reviewer cannot
        # see. The bounce itself stands and a later push carries the commit.
        gh, issue = self._seed_stranded_bounce()

        mocks = self._run_stranded_bounce(
            gh,
            issue,
            TEMP_ROOT,
            branch_ahead_behind=(1, 0),
            push_branch=False,
        )

        mocks[PUSH_BRANCH].assert_called_once()
        self._assert_bounced(gh, round_n=SEEDED_ROUND)

    def _assert_bounced(self, gh, *, round_n: int) -> None:
        """The bounce always lands: bookmarks dropped, back to `validating`."""
        pinned_data = gh.pinned_data(ISSUE)
        self.assertEqual(pinned_data.get(REVIEW_ROUND), round_n)
        self.assertIsNone(pinned_data.get(PENDING_FIX_REVIEWER_COMMENT_ID))
        self.assertIn((ISSUE, VALIDATING), gh.label_history)


if __name__ == "__main__":
    unittest.main()
