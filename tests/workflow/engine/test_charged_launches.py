# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Every developer and reviewer process start is charged to its own issue.

One boundary takes the charge, so what is worth driving real handlers for is
whether each road reaches it carrying the issue it is spending. A stage that
named some other budget would still spawn and still charge something, and no
assertion about the circuit alone would notice; a spend read off this issue's
own pinned comment afterwards is what does.

Read afterwards on purpose. The charge lands on freshly read durable state in
the middle of a tick, and the handler writes again at the end of one, out of
the object it has been holding since before the spawn. So the count surviving
that write is half of what these cases pin down, and the relabel each road
leaves behind is what says the write happened at all.

The other half is the two roads whose outcome is thrown away. A run the
shutdown sweep killed and a run an operator paused mid-flight both return
before anything is disposed, and both cost the same minutes of somebody's
compute as a run that finished -- so the charge stands where the disposition
does not, and the ceiling counts the attempts an issue actually made rather
than the ones that happened to come back.
"""
from __future__ import annotations

import contextlib
import unittest
from unittest.mock import MagicMock, patch

from orchestrator.github.labels import PAUSED_LABEL
from tests.support.fakes import FakeGitHubClient, FakeLabel, make_issue
from tests.workflow.engine import charged_run_roads as roads, charged_run_test_support as support
from tests.workflow.fixtures import _agent, _PatchedWorkflowMixin

# What the shutdown sweep leaves behind: no session, nothing said, and a flag
# saying none of it can be trusted.
_INTERRUPTED = _agent(session_id=None, last_message="", interrupted=True)

# What a resume lands on when the backend has lost the transcript it names.
_POISONED = _agent(
    session_id=None, last_message="", stderr=support.POISONED_STDERR,
)


@contextlib.contextmanager
def _paused_mid_run(road):
    """An operator applying `paused` while this road's process is out.

    Patched onto the client class rather than one instance because the road
    builds its own, and what the guard reads is a FRESH fetch -- which is the
    whole point: the labels the handler holds were read before the spawn.
    """
    view = make_issue(road.number, label=road.label)
    view.labels.append(FakeLabel(PAUSED_LABEL))
    with patch.object(
        FakeGitHubClient, "get_issue", MagicMock(return_value=view),
    ) as fetched:
        yield fetched


class ChargedLaunchTest(unittest.TestCase, _PatchedWorkflowMixin):
    """No road reaches a process without spending one of the issue's runs."""

    def test_every_road_charges_the_issue_it_spends(self) -> None:
        for road in roads.ROADS:
            with self.subTest(role=road.role):
                driven = road.drive(self, road.agent_result)

                self.assertEqual(driven.spawns, 1)
                self._assert_charged(driven, launches=1)
                # The tick reached its own disposition and wrote it, and the
                # charge is still on the issue on the far side of that write.
                self.assertNotEqual(driven.github.label_history, [])

    def test_a_poisoned_session_pays_for_both_spawns(self) -> None:
        # The resume lands on a transcript the backend no longer has, which
        # buys a second process in the same tick -- a fresh spawn in the same
        # worktree. Two launches, two charges: a retry the ledger saw once
        # would be a way to spend a lifetime two runs at a time.
        driven = roads.IMPLEMENTING_RESUME.drive(self, _POISONED)

        self.assertEqual(driven.spawns, 2)
        self._assert_charged(driven, launches=2)

    def test_an_interrupted_launch_stays_charged(self) -> None:
        for road in roads.ROADS:
            with self.subTest(role=road.role):
                driven = road.drive(self, _INTERRUPTED)

                self.assertEqual(driven.spawns, 1)
                self._assert_charged(driven, launches=1)
                self._assert_nothing_disposed(driven)

    def test_a_paused_launch_stays_charged(self) -> None:
        for road in roads.ROADS:
            with self.subTest(role=road.role):
                with _paused_mid_run(road) as fetched:
                    driven = road.drive(self, road.agent_result)
                    fetched.assert_called_with(road.number)

                self.assertEqual(driven.spawns, 1)
                self._assert_charged(driven, launches=1)
                self._assert_nothing_disposed(driven)

    def _assert_charged(self, driven, *, launches: int) -> None:
        """The issue durably paid for every process this tick invoked."""
        self.assertEqual(driven.spent, support.SPENT_BEFORE + launches)
        self.assertEqual(driven.reservation, support.STARTED)

    def _assert_nothing_disposed(self, driven) -> None:
        """A run whose outcome was declined published none of it."""
        self.assertEqual(driven.github.label_history, [])
        self.assertEqual(driven.github.posted_comments, [])
        self.assertFalse(driven.mocks[support.PUSH_BRANCH].called)


if __name__ == "__main__":
    unittest.main()
