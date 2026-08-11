# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A dispatched `discussion` tick leaves the issue exactly as it found it."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.agents import runner as _agent_runner
from orchestrator.workflow.engine import dispatch as _dispatch

from tests.support.fakes import FakeGitHubClient, make_issue
from tests.workflow.fixtures import LABEL_DISCUSSION, _TEST_SPEC

_OPEN_ISSUE_NUMBER = 902

_CLOSED_ISSUE_NUMBER = 903

_RUN_AGENT = "run_agent"


class DiscussionHandlerTest(unittest.TestCase):
    """The hold is inert on both sides of the issue's own lifecycle.

    An operator applies the label to stop the orchestrator, so the tick has to
    be observationally empty: a relabel, a comment, or a pinned-state write
    would each be the orchestrator acting on an issue humans are still settling
    between themselves. Closing such an issue is not a terminal signal either --
    the stage has no arc to finalize, so the only thing that ends the hold is a
    human relabel.
    """

    def test_a_tick_writes_nothing(self) -> None:
        for issue_number, closed in (
            (_OPEN_ISSUE_NUMBER, False), (_CLOSED_ISSUE_NUMBER, True),
        ):
            with self.subTest(closed=closed):
                self._assert_tick_is_inert(issue_number, closed)

    def _assert_tick_is_inert(self, issue_number: int, closed: bool) -> None:
        gh = FakeGitHubClient()
        issue = make_issue(issue_number, label=LABEL_DISCUSSION)
        issue.closed = closed
        gh.add_issue(issue)

        # The spawn seam is patched rather than trusted: an agent run is the
        # one side effect a stage handler can have without touching the issue.
        with patch.object(_agent_runner, _RUN_AGENT) as run_agent:
            _dispatch._process_issue(gh, _TEST_SPEC, issue)
            run_agent.assert_not_called()

        self.assertEqual(gh.label_history, [])
        self.assertEqual(gh.posted_comments, [])
        self.assertEqual(gh.write_state_calls, 0)
        self.assertEqual(gh.recorded_events, [])
        self.assertEqual(
            [label.name for label in issue.labels], [LABEL_DISCUSSION],
        )
        self.assertEqual(issue.closed, closed)


if __name__ == "__main__":
    unittest.main()
