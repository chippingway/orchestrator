# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The four ways an opening round ends somewhere other than a design.

A timeout and a silent exit are the agent failing to say anything; commits and
a dirty tree are it saying something by doing, which this stage does not allow
-- a discussion that starts editing has skipped the human confirmation the
whole stage waits for. All four park awaiting a human with their own reason, so
an operator reading pinned state can tell which happened, and all four keep the
worktree, because in every one of them there is something on disk worth
looking at.
"""

from __future__ import annotations

import unittest

from orchestrator import config

from tests.workflow.fixtures import (
    KEY_AWAITING_HUMAN,
    KEY_PARK_REASON,
    _agent,
)

from tests.workflow.stages.discussion.discussion_test_support import (
    DIRTY_DISPLAY_LIMIT,
    DIRTY_FILE_COUNT,
    DIRTY_OVERFLOW_COUNT,
    DISCUSSION_RESPONSE,
    DISCUSSION_SESSION,
    MOVED_HEAD,
    PARK_DISCUSSION_COMMITS,
    PARK_DISCUSSION_DIRTY,
)
from tests.workflow.stages.discussion.discussion_test_support import (
    PARK_DISCUSSION_RESPONSE,
    PARK_DISCUSSION_SILENT,
    PARK_DISCUSSION_TIMEOUT,
    RUN_AGENT,
    _DiscussionWorkflowMixin,
)
from tests.workflow.stages.discussion.discussion_test_support import (
    HEAD_BEFORE_ROUND,
    KEY_ROUND_SHA,
    _dirty_files,
    _seed_discussion,
)

_TIMEOUT_ISSUE_NUMBER = 920
_COMMITS_ISSUE_NUMBER = 921
_DIRTY_ISSUE_NUMBER = 922
_SILENT_ISSUE_NUMBER = 923
_INTERRUPTED_COMMITS_ISSUE_NUMBER = 924
_INHERITED_COMMITS_ISSUE_NUMBER = 925
_AGENT_STDERR = "backend refused the session"
_LAST_SHOWN_FILE = DIRTY_DISPLAY_LIMIT - 1


class DiscussionParkTest(unittest.TestCase, _DiscussionWorkflowMixin):
    """Each unhappy exit and the reason it parks under."""

    def test_timeout_parks_and_names_the_budget(self) -> None:
        gh, issue = _seed_discussion(_TIMEOUT_ISSUE_NUMBER)

        mocks = self._run_discussion(
            gh,
            issue,
            run_agent=_agent(
                session_id=DISCUSSION_SESSION,
                last_message="half a thought",
                timed_out=True,
            ),
        )

        body = self._assert_parked(
            gh, mocks, issue.number, PARK_DISCUSSION_TIMEOUT,
        )
        self.assertIn(f"{config.AGENT_TIMEOUT}s", body)
        # A killed round's partial reasoning is not a design to reply to.
        self.assertNotIn("half a thought", body)

    def test_commits_park_before_the_response(self) -> None:
        gh, issue = _seed_discussion(_COMMITS_ISSUE_NUMBER)

        mocks = self._run_discussion(
            gh,
            issue,
            run_agent=_agent(
                session_id=DISCUSSION_SESSION,
                last_message=DISCUSSION_RESPONSE,
            ),
            head_shas=MOVED_HEAD,
        )

        body = self._assert_parked(
            gh, mocks, issue.number, PARK_DISCUSSION_COMMITS,
        )
        # What it wrote outranks what it said: the analysis is not published
        # as a design when the agent has already started building one.
        self.assertNotIn(DISCUSSION_RESPONSE, body)
        # The park names the tip to reset back to and keeps it recorded. On a
        # PR-backed branch "reset the worktree" read as "reset to base" would
        # take the PR's commits with the agent's, and the relabel guard has
        # nothing left to certify the survivors by.
        self.assertIn(HEAD_BEFORE_ROUND, body)
        self.assertEqual(
            gh.pinned_data(issue.number)[KEY_ROUND_SHA], HEAD_BEFORE_ROUND,
        )

    def test_inherited_commits_do_not_park(self) -> None:
        # An issue relabeled here from a PR stage arrives with its dev's
        # commits already ahead of base. HEAD does not move under this round,
        # so those are not its doing and the analysis is published normally.
        gh, issue = _seed_discussion(_INHERITED_COMMITS_ISSUE_NUMBER)

        mocks = self._run_discussion(
            gh,
            issue,
            run_agent=_agent(
                session_id=DISCUSSION_SESSION,
                last_message=DISCUSSION_RESPONSE,
            ),
            has_new_commits=True,
        )

        body = self._assert_parked(
            gh, mocks, issue.number, PARK_DISCUSSION_RESPONSE,
        )
        self.assertIn(DISCUSSION_RESPONSE, body)
        mocks[RUN_AGENT].assert_called_once()

    def test_dirty_tree_parks_with_bounded_paths(self) -> None:
        gh, issue = _seed_discussion(_DIRTY_ISSUE_NUMBER)

        mocks = self._run_discussion(
            gh,
            issue,
            run_agent=_agent(
                session_id=DISCUSSION_SESSION,
                last_message=DISCUSSION_RESPONSE,
            ),
            dirty_files=_dirty_files(),
        )

        body = self._assert_parked(
            gh, mocks, issue.number, PARK_DISCUSSION_DIRTY,
        )
        self.assertIn(f"{DIRTY_FILE_COUNT} uncommitted change(s)", body)
        self.assertIn(f"- `file_{_LAST_SHOWN_FILE}.py`", body)
        self.assertNotIn(f"- `file_{DIRTY_DISPLAY_LIMIT}.py`", body)
        self.assertIn(f"- ... ({DIRTY_OVERFLOW_COUNT} more)", body)

    def test_silence_parks_with_stderr_diagnostics(self) -> None:
        gh, issue = _seed_discussion(_SILENT_ISSUE_NUMBER)

        mocks = self._run_discussion(
            gh,
            issue,
            run_agent=_agent(
                session_id="",
                last_message="   ",
                exit_code=1,
                stderr=_AGENT_STDERR,
            ),
        )

        body = self._assert_parked(
            gh, mocks, issue.number, PARK_DISCUSSION_SILENT,
        )
        self.assertIn(_AGENT_STDERR, body)

    def test_killed_round_parks_on_what_it_wrote(self) -> None:
        # The read-only checks run before the interruption check, so a round
        # the shutdown sweep killed mid-edit still leaves the operator a park
        # and a tree instead of vanishing as an untrustworthy run.
        gh, issue = _seed_discussion(_INTERRUPTED_COMMITS_ISSUE_NUMBER)

        mocks = self._run_discussion(
            gh,
            issue,
            run_agent=_agent(
                session_id=DISCUSSION_SESSION,
                last_message="",
                interrupted=True,
            ),
            head_shas=MOVED_HEAD,
        )

        self._assert_parked(gh, mocks, issue.number, PARK_DISCUSSION_COMMITS)

    def _assert_parked(self, gh, mocks, issue_number: int, reason: str) -> str:
        self.assert_nothing_published(gh, mocks)
        self.assert_worktree_preserved(mocks)
        pinned_data = gh.pinned_data(issue_number)
        self.assertTrue(pinned_data[KEY_AWAITING_HUMAN])
        self.assertEqual(pinned_data[KEY_PARK_REASON], reason)
        self.assertEqual(len(gh.posted_comments), 1)
        _, body = gh.posted_comments[0]
        self.assertIn(config.HITL_MENTIONS, body)
        return body


if __name__ == "__main__":
    unittest.main()
