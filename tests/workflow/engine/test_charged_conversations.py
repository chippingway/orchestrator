# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Every decomposition and conversation process start is charged to its issue.

One boundary takes the charge, so what is worth driving real handlers for is
whether each road reaches it carrying the issue it is spending. A stage that
named some other budget would still spawn and still charge something, and no
assertion about the circuit alone would notice; a spend read off this issue's
own pinned comment afterwards is what does.

Read afterwards on purpose. The charge lands on freshly read durable state in
the middle of a tick, and the handler writes again at the end of one, out of
the object it has been holding since before the spawn. So the count surviving
that write is half of what these cases pin down.

The other half is what the charge may NOT carry out with it. These three
stages each stage something ahead of their spawn that only their own
disposition is allowed to publish, and the reply batch a resumed round marks
as read is the sharpest of them: a round that never reports is replayed, and
it has to be replayed against the same replies rather than against an answer
already recorded as read. So a round an operator pauses mid-flight is driven
here too, and what it must leave behind is exactly the charge and nothing
else -- the watermark still where the park put it, and the humans still
waiting on the round that was interrupted.
"""
from __future__ import annotations

import unittest

from tests.workflow.engine import (
    charged_conversation_roads as roads,
    charged_run_test_support as support,
)
from tests.workflow.fixtures import (
    KEY_LAST_ACTION_COMMENT_ID,
    _PatchedWorkflowMixin,
)


class ChargedConversationTest(unittest.TestCase, _PatchedWorkflowMixin):
    """No talking road reaches a process without spending one of the runs."""

    def test_every_road_charges_the_issue_it_spends(self) -> None:
        for road in roads.ROADS:
            with self.subTest(role=road.role):
                driven = road.drive(self, road.agent_result)

                self.assertEqual(driven.spawns, 1)
                self._assert_charged(driven)

    def test_an_interrupted_launch_stays_charged(self) -> None:
        # A run the shutdown sweep killed cost the same minutes of somebody's
        # compute as one that finished, and its whole outcome is thrown away.
        for road in roads.ROADS:
            with self.subTest(role=road.role):
                driven = road.drive(self, support.INTERRUPTED)

                self.assertEqual(driven.spawns, 1)
                self._assert_charged(driven)

    def test_a_paused_launch_stays_charged(self) -> None:
        for road in roads.ROADS:
            with self.subTest(role=road.role):
                with support.paused_mid_run(road) as fetched:
                    driven = road.drive(self, road.agent_result)
                    fetched.assert_called_with(road.number)

                self.assertEqual(driven.spawns, 1)
                self._assert_charged(driven)
                self.assertEqual(driven.github.label_history, [])
                self.assertEqual(driven.github.posted_comments, [])

    def test_a_paused_round_leaves_its_replies_unread(self) -> None:
        # The one thing the charge may not carry out of the tick with it. Each
        # resumed round marks the batch it quotes as read BEFORE it spawns, so
        # a charge that flushed the caller's object would publish an answer as
        # already-read on a round that never reported one -- and the humans
        # would wait forever on a reply the next tick no longer sees.
        for road in roads.RESUMED_ROADS:
            with self.subTest(role=road.role):
                with support.paused_mid_run(road):
                    driven = road.drive(self, road.agent_result)

                self._assert_charged(driven)
                self.assertEqual(
                    driven.github.pinned_data(road.number).get(
                        KEY_LAST_ACTION_COMMENT_ID,
                    ),
                    roads.PARKED_WATERMARK,
                )

    def _assert_charged(self, driven) -> None:
        """The issue durably paid for the process this tick invoked."""
        self.assertEqual(driven.spent, support.SPENT_BEFORE + 1)
        self.assertEqual(driven.reservation, support.STARTED)


if __name__ == "__main__":
    unittest.main()
