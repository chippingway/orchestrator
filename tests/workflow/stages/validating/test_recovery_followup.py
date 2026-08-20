# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest

from orchestrator.workflow.stages.validating import recovery as _recovery

from tests.support.fakes import FakeComment, FakeGitHubClient, make_issue
from tests.workflow import fixtures as _fixtures

AGENT_TIMEOUT = _fixtures.AGENT_TIMEOUT_PARK
LAST_ACTION_COMMENT_ID = _fixtures.LAST_ACTION_COMMENT_ID
NO_ACTION_LINE = _fixtures.NO_ACTION_LINE
OUTCOME_CLEARED = _fixtures.OUTCOME_CLEARED
OUTCOME_PUSHED = _fixtures.OUTCOME_PUSHED
PUSH_FAILED = _fixtures.PUSH_FAILED_PARK
PUSH_RETRIED_DETAIL = _fixtures.PUSH_RETRIED_DETAIL
RECOVERED_PREFIX = _fixtures.RECOVERED_PREFIX
REVIEWER_FAILED = _fixtures.REVIEWER_FAILED_PARK
REVIEWER_RESPAWN_DETAIL = _fixtures.REVIEWER_RESPAWN_DETAIL
REVIEWER_TIMEOUT = _fixtures.REVIEWER_TIMEOUT_PARK
TIMEOUT_EMPTY_DETAIL = _fixtures.TIMEOUT_EMPTY_DETAIL
TIMEOUT_PUSHED_DETAIL = _fixtures.TIMEOUT_PUSHED_DETAIL

FOLLOWUP_ISSUE = 640
MENTION_COMMENT_ID = 500
FOLLOWUP_COMMENT_ID = 600
LATER_MENTION_COMMENT_ID = 700


class RecoveryFollowupCommentTest(unittest.TestCase):
    """Word the follow-up from the park reason and the recovery outcome."""

    def setUp(self) -> None:
        self.github = FakeGitHubClient()
        self.issue = make_issue(FOLLOWUP_ISSUE, label="workflow:validating")
        self.github.add_issue(self.issue)
        self.github.seed_state(
            FOLLOWUP_ISSUE, **{LAST_ACTION_COMMENT_ID: MENTION_COMMENT_ID},
        )

    def test_wording_names_what_healed(self) -> None:
        healed = (
            (PUSH_FAILED, OUTCOME_PUSHED, PUSH_RETRIED_DETAIL),
            (AGENT_TIMEOUT, OUTCOME_PUSHED, TIMEOUT_PUSHED_DETAIL),
            (AGENT_TIMEOUT, OUTCOME_CLEARED, TIMEOUT_EMPTY_DETAIL),
            (REVIEWER_TIMEOUT, OUTCOME_CLEARED, REVIEWER_RESPAWN_DETAIL),
            (REVIEWER_FAILED, OUTCOME_CLEARED, REVIEWER_RESPAWN_DETAIL),
        )
        for park_reason, outcome, detail in healed:
            with self.subTest(park_reason=park_reason, outcome=outcome):
                body = self._followup(park_reason, outcome)
                self.assertIn(RECOVERED_PREFIX, body)
                self.assertIn(detail, body)
                self.assertIn(NO_ACTION_LINE, body)
                # The park already pinged a human; closing the loop must
                # not ping a second time.
                self.assertNotIn("@", body)

    def test_no_wording_leaves_the_thread_alone(self) -> None:
        # Without `last_action_comment_id` the park never mentioned anybody,
        # so there is no alarming last word to retire. A reason paired with
        # an outcome it cannot reach (`push_failed` never clears without
        # pushing) and a reason outside the transient set have no sentence
        # that describes them, so they say nothing rather than guess.
        self.github.seed_state(FOLLOWUP_ISSUE)
        self.assertIsNone(self._followup(PUSH_FAILED, OUTCOME_PUSHED))
        self.github.seed_state(
            FOLLOWUP_ISSUE, **{LAST_ACTION_COMMENT_ID: MENTION_COMMENT_ID},
        )
        self.assertIsNone(self._followup(PUSH_FAILED, OUTCOME_CLEARED))
        self.assertIsNone(self._followup(None, OUTCOME_CLEARED))

    def test_the_thread_is_the_at_most_once_receipt(self) -> None:
        # The posted follow-up is the only record that survives a pinned
        # write that never landed, so a repeat attempt for the same episode
        # recognizes it on the thread and says nothing. Recognition is scoped
        # by `last_action_comment_id`: the NEXT park stamps a higher one, and
        # the follow-up now sitting below it must not silence that episode.
        self._post(self._followup(PUSH_FAILED, OUTCOME_PUSHED))
        self.assertIsNone(self._followup(PUSH_FAILED, OUTCOME_PUSHED))

        self.github.seed_state(
            FOLLOWUP_ISSUE, **{LAST_ACTION_COMMENT_ID: LATER_MENTION_COMMENT_ID},
        )
        self.assertIn(
            PUSH_RETRIED_DETAIL, self._followup(PUSH_FAILED, OUTCOME_PUSHED),
        )

    def _post(self, body: str) -> None:
        self.issue.comments.append(
            FakeComment(id=FOLLOWUP_COMMENT_ID, body=body),
        )

    def _followup(self, park_reason, outcome: str):
        return _recovery._recovery_followup_comment(
            self.github,
            self.issue,
            self.github.read_pinned_state(self.issue),
            park_reason,
            outcome,
        )
