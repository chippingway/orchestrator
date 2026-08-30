# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A reading of the branch that did not happen, on both documenting roads.

The fetch lands and the reading behind it does not: a ref nothing could
resolve, a comparison git refused, a count in a shape nothing can parse. Every
one of them answers zero and zero -- which is exactly what an IN-SYNC branch
answers, and the two may not be collapsed.

Read as in sync, the fresh road spawns a docs agent over a checkout whose
relationship to the pull request nobody established and force-pushes what it
writes; the recovered road pushes WITHOUT spawning, since the ahead count is
what licenses that push. And the head both are pinned to comes from the same
reading, so an unread one leaves it empty -- which has the size gate adopt
whatever the pull request has moved to and lease the force-push against that.
"""
from __future__ import annotations

import unittest

from tests.workflow.fixtures import _agent
from tests.workflow.stages.documenting import (
    documenting_test_support as documenting_support,
)
from tests.workflow.stages.documenting.documenting_test_support import (
    AWAITING_HUMAN,
    IN_REVIEW,
    PARK_REASON,
    PUSH_BRANCH,
    RUN_AGENT,
    VALIDATING,
    _FreshDocumentingFixture,
)


class HandleDocumentingUnreadDivergenceTest(
    _FreshDocumentingFixture, unittest.TestCase,
):
    """Both roads hold, and neither spawns or pushes over what it cannot read."""

    def test_an_unread_divergence_holds_a_spawn(self) -> None:
        # The fresh road: no docs commit waiting, so what this stops is the
        # agent run and the push behind it.
        self._assert_held(self._unread(ahead=0), spawned=False)

    def test_an_unread_divergence_holds_a_push(self) -> None:
        # The recovered road, which is the one that would push WITHOUT
        # spawning: the ahead count and the head the push replaces come from
        # this one reading, so a count nobody took cannot license the push
        # and an unnamed head cannot pin it.
        self._assert_held(self._unread(ahead=1))

    def _unread(self, *, ahead: int):
        """One docs tick whose divergence reading established nothing."""
        github, issue = self._seeded()
        mocks = self._run_documenting(
            github,
            issue,
            run_agent=_agent(),
            push_branch=True,
            head_shas=[],
            branch_ahead_behind=(ahead, 0),
            branch_divergence_readable=False,
        )
        return github, mocks

    def _assert_held(self, ran, *, spawned: bool = True) -> None:
        """Nothing pushed, nothing handed on, and a human asked for."""
        github, mocks = ran
        mocks[PUSH_BRANCH].assert_not_called()
        if not spawned:
            mocks[RUN_AGENT].assert_not_called()
        self.assertNotIn((self.issue_number, IN_REVIEW), github.label_history)
        self.assertNotIn((self.issue_number, VALIDATING), github.label_history)
        parked = github.pinned_data(self.issue_number)
        self.assertTrue(parked.get(AWAITING_HUMAN))
        self.assertEqual(
            parked.get(PARK_REASON),
            documenting_support.PARK_UNREADABLE_DIVERGENCE,
        )


if __name__ == "__main__":
    unittest.main()
