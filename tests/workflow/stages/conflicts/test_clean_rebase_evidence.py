# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A clean rebase whose own evidence nobody could read.

Both readings this exit turns on answer the way an ordinary world does when
they fail: a status that established nothing names no paths, which is exactly
what a tree with nothing in it names, and a head that would not resolve reads
as the head the stage started on. Taken as absences they are the two ways a
clean rebase hands a reviewer a checkout that was never proved -- a tree
carrying content the pull request does not have, or a rewritten head it never
received.
"""
from __future__ import annotations

import unittest

from tests.workflow.stages.conflicts.conflicts_test_support import (
    CONFLICT_PR_HEAD_SHA,
    _ResolvingConflictMixin,
)

CONFLICT_ISSUE = 200

# The pre-rebase head this stage reads for itself, and the head a rebase that
# moved nothing leaves the checkout on.
BEFORE_HEAD = CONFLICT_PR_HEAD_SHA
UNCHANGED_HEAD = BEFORE_HEAD

# What `git rev-parse HEAD` reports when it could not answer at all.
UNREADABLE_HEAD = ""

PUSH_BRANCH = "_push_branch"
AWAITING_HUMAN = "awaiting_human"
CONFLICT_ROUND = "conflict_round"
LABEL_VALIDATING = "workflow:validating"

# The reason a `resolving_conflict` refusal records. It rides the
# `park_awaiting_human` audit event rather than the pinned comment, which
# `_park_awaiting_human` deliberately clears.
EVENT_PARKED = "park_awaiting_human"
PARK_UNREADABLE_WORKTREE = "unreadable_worktree"
PARK_UNREADABLE_HEAD = "unreadable_head"


class CleanRebaseUnprovenEvidenceTest(
    unittest.TestCase, _ResolvingConflictMixin,
):
    """Neither clean-rebase exit may be taken on a reading that failed."""

    def test_a_tree_nobody_read_parks(self) -> None:
        # Read as an absence, the no-op flip carries the worktree into
        # validating untouched, where the reviewer reads the tree directly --
        # so an uncommitted edit nothing could see becomes a vote against
        # content the pull request does not carry, and the in_review
        # ready-ping advertises that approval to a human merger.
        github, issue = self._seed()[:2]

        mocks = self._rebased(
            github, issue,
            head_shas=[UNCHANGED_HEAD, UNCHANGED_HEAD],
            tree_readable=False,
        )

        self._assert_refused(github, mocks, PARK_UNREADABLE_WORKTREE)

    def test_a_head_nobody_read_parks(self) -> None:
        # Read as "the base had not moved", the round goes back to validating
        # with nothing having established whether the rebase left a rewritten
        # head the pull request never received -- and no later tick goes back
        # for it, since the branch it comes back to already carries its base.
        github, issue = self._seed()[:2]

        mocks = self._rebased(
            github, issue, head_shas=[BEFORE_HEAD, UNREADABLE_HEAD],
        )

        self._assert_refused(github, mocks, PARK_UNREADABLE_HEAD)

    def _rebased(self, github, issue, **run_options):
        """One tick whose `git rebase` came back clean."""
        return self._run_with_merge(
            github, issue,
            merge_succeeded=True,
            push_branch=True,
            **run_options,
        )[0]

    def _assert_refused(self, github, mocks, reason: str) -> None:
        """Nothing pushed, no round counted, and the issue left for a human."""
        mocks[PUSH_BRANCH].assert_not_called()
        self.assertNotIn(
            (CONFLICT_ISSUE, LABEL_VALIDATING), github.label_history,
        )
        pinned = github.pinned_data(CONFLICT_ISSUE)
        self.assertTrue(pinned.get(AWAITING_HUMAN))
        self.assertEqual(pinned.get(CONFLICT_ROUND), 0)
        self.assertEqual(self._recorded(github, EVENT_PARKED), [reason])
        self.assertEqual(self._recorded(github, CONFLICT_ROUND), [])

    def _recorded(self, github, event_name: str) -> list:
        """What each event of this name reported, in emission order."""
        return [
            event.get("reason") or event.get("action")
            for event in github.recorded_events
            if event.get("event") == event_name
        ]


if __name__ == "__main__":
    unittest.main()
