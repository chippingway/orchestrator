# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one park the dispatcher answers instead of the stage its label names.

An issue that has spent every agent run it is allowed is stopped for good, and
`awaiting_human` means something different on every road below: a resume on
the next trusted reply, a hold waiting on guidance, a classifier that refuses
a command carrying none. Each of those is right about the park it was written
against and none of them buys back a run, so the park is held once, ahead of
the table.

The exemption is the other half of it. What a CLOSED issue reaches below is a
terminal that ends it rather than a road that spends anything on it, so the
hold steps aside and lets the ending finish.
"""
from __future__ import annotations

import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from orchestrator.workflow.engine import dispatch
from tests.support.fakes import FakeGitHubClient, make_issue
from tests.workflow.engine import run_limit_test_support as support
from tests.workflow.fixtures import LABEL_IMPLEMENTING

_SPEC = SimpleNamespace(slug="acme/widget")


class _HoldCase:
    """One issue routed by label, with the stage handler it names patched."""

    def setUp(self) -> None:
        self.gh = FakeGitHubClient()
        self.reached = Mock()

    def _issue(self, *, closed: bool = False):
        issue = make_issue(
            support.ISSUE_NUMBER, label=LABEL_IMPLEMENTING, closed=closed,
        )
        self.gh.add_issue(issue)
        return issue

    def _route(self, issue, *, reading=dispatch._POLLED_OPEN) -> None:
        module_name, handler_name = dispatch._STAGE_HANDLER_TARGETS[
            LABEL_IMPLEMENTING
        ]
        with patch.object(
            importlib.import_module(module_name), handler_name, self.reached,
        ):
            dispatch._route_issue_to_handler(
                self.gh, _SPEC, issue, LABEL_IMPLEMENTING, reading=reading,
            )


class RunLimitHoldTest(_HoldCase, unittest.TestCase):
    """What a spent lifetime ledger stops, and what it lets through."""

    def test_a_parked_issue_reaches_no_handler(self) -> None:
        issue = self._issue()
        self._seed(support.parked_state())

        self._route(issue)

        self.reached.assert_not_called()
        # A park nobody can see going on refusing reads as a workflow that
        # stopped for no reason.
        self.assertEqual(support.phases(self.gh), [support.STANDING])

    def test_a_closed_issue_completes_its_ending(self) -> None:
        # The terminal below ends the issue rather than spending a run on it,
        # and a refusal here would leave it permanently mid-ending.
        issue = self._issue(closed=True)
        self._seed(support.parked_state())

        self._route(issue)

        self.reached.assert_called_once_with(self.gh, _SPEC, issue)
        self.assertEqual(support.phases(self.gh), [])

    def test_the_polls_own_closed_reading_counts(self) -> None:
        # The issue this tick was routed on was closed when it was
        # enumerated, whatever the object in hand now reads as.
        issue = self._issue()
        self._seed(support.parked_state())

        self._route(issue, reading=dispatch._PollReading(closed=True))

        self.reached.assert_called_once_with(self.gh, _SPEC, issue)

    def test_another_park_is_not_this_one(self) -> None:
        # `awaiting_human` alone is every stage's park, and each of those has
        # a road of its own below that answers it.
        issue = self._issue()
        self._seed(support.state_with(**{
            support.AWAITING_HUMAN: True, support.PARK_REASON: "retry_cap",
        }))

        self._route(issue)

        self.reached.assert_called_once_with(self.gh, _SPEC, issue)

    def _seed(self, state) -> None:
        self.gh.seed_state(support.ISSUE_NUMBER, **state.data)


class RunLimitNoticeTest(_HoldCase, unittest.TestCase):
    """The sentence the hold says, and the ticks that say nothing more."""

    def test_an_owed_sentence_is_replayed(self) -> None:
        # Nothing below the hold runs, so a notice a refused post left owed
        # would be owed for as long as the issue is parked.
        issue = self._parked_issue()

        self._route(issue)

        self.reached.assert_not_called()
        posted = self.gh.posted_comments[-1][1]
        self.assertIn(support.notice_text(), posted)
        self.assertNotIn(
            support.NOTICE, self.gh.pinned_data(support.ISSUE_NUMBER),
        )
        self.assertEqual(
            support.phases(self.gh), [support.DELIVERED, support.STANDING],
        )

    def test_a_said_sentence_is_not_repeated(self) -> None:
        issue = self._parked_issue()
        polls = 3

        for _ in range(polls):
            self._route(issue)

        said = support.phases(self.gh)
        self.assertEqual(len(self.gh.posted_comments), 1)
        self.assertEqual(len(said), polls + 1)
        self.assertEqual(said[0], support.DELIVERED)
        self.assertEqual(set(said[1:]), {support.STANDING})

    def _parked_issue(self):
        issue = self._issue()
        self.gh.seed_state(
            support.ISSUE_NUMBER, **support.parked_state(owing=True).data,
        )
        return issue


class HoldPlacementTest(unittest.TestCase):
    """Where in the guard chain the hold sits, and what that costs.

    Behind the pair that RUN, because a cancelled cycle still holding a branch
    and a restart an operator authorized are endings rather than work: parked
    behind this hold they would be owed for as long as the issue is stopped,
    which on a lifetime total is for good.
    """

    def test_a_restart_outranks_the_hold(self) -> None:
        gh = FakeGitHubClient()
        issue = make_issue(support.ISSUE_NUMBER, label=LABEL_IMPLEMENTING)
        gh.add_issue(issue)
        gh.seed_state(support.ISSUE_NUMBER, **support.parked_state().data)
        restart = Mock(return_value=True)

        with patch.object(
            importlib.import_module(dispatch._LATE_RESTART_OWNER),
            "_restarts", restart,
        ):
            held = dispatch._pinned_state_refuses(
                gh, _SPEC, issue, LABEL_IMPLEMENTING,
            )

        self.assertTrue(held)
        restart.assert_called_once()
        self.assertEqual(support.phases(gh), [])


if __name__ == "__main__":
    unittest.main()
