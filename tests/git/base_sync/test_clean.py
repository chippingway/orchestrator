# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What `publication` publishes on a clean rebase, and what `guards` refuse."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.workflow.engine import dispatch as _dispatch
from orchestrator.workflow.stages.in_review import handler as _in_review

from tests.git.base_sync.refresh_scenarios import (
    PUSH_PATCH,
    _clean_rebase_scenario,
    _conflict_rebase_scenario,
)
from tests.git.base_sync.refresh_test_support import (
    _AwaitingHumanRecorder,
    _SyncWorktreeWithBaseFixture,
)
from tests.support.fakes import FakePRRef

from tests.git.base_sync.clean_assertions import (
    _assert_clean_events,
    _assert_clean_publication,
    _assert_clean_state_comments,
    _assert_conflict_publication,
    _assert_conflict_state_event,
    _assert_push_failure_git,
    _assert_push_failure_state,
)

ISSUE = 7

# Remote PR head planted so the conflict-round event can assert its `sha`.
CONFLICT_PR_HEAD_SHA = "cafef00dcafef00d"

# Workflow labels the publication routes between.
LABEL_VALIDATING = "validating"
LABEL_RESOLVING_CONFLICT = "resolving_conflict"
LABEL_DOCUMENTING = "documenting"

THREE_BEHIND_STDOUT = "3\n"


class CleanRebaseRoutingUnitTest(_SyncWorktreeWithBaseFixture, unittest.TestCase):
    def test_in_review_rebase_routes_to_validating(self) -> None:
        self._seed_pr_issue(review_round=3)
        self._add_pr()
        scenario = _clean_rebase_scenario(THREE_BEHIND_STDOUT)

        scenario.run(self)

        _assert_clean_publication(self, self, scenario)
        _assert_clean_state_comments(self, self)
        _assert_clean_events(self, self)

    def test_conflict_rebase_routes_to_resolution(self) -> None:
        self._seed_pr_issue()
        self._add_pr(head=FakePRRef(sha=CONFLICT_PR_HEAD_SHA))
        scenario = _conflict_rebase_scenario()

        scenario.run(self)

        _assert_conflict_publication(self, self, scenario)
        _assert_conflict_state_event(self, self)

    def test_validating_rebase_stays_validating(self) -> None:
        self._seed_pr_issue(label=LABEL_VALIDATING)
        self._add_pr()
        scenario = _clean_rebase_scenario()

        scenario.run(self)

        self.assertIn((ISSUE, LABEL_VALIDATING), self.gh.label_history)
        self.assertNotIn(
            (ISSUE, LABEL_RESOLVING_CONFLICT),
            self.gh.label_history,
        )
        scenario[PUSH_PATCH].assert_called_once()

    def test_documenting_rebase_routes_to_validating(self) -> None:
        self._seed_pr_issue(label=LABEL_DOCUMENTING)
        self._add_pr()

        _clean_rebase_scenario().run(self)

        self.assertIn((ISSUE, LABEL_VALIDATING), self.gh.label_history)
        self.assertNotIn(
            (ISSUE, LABEL_RESOLVING_CONFLICT),
            self.gh.label_history,
        )

    def test_clean_push_failure_resets_and_parks(self) -> None:
        self._seed_pr_issue()
        self._add_pr()
        scenario = _clean_rebase_scenario(push_result=False)

        scenario.run(self)

        _assert_push_failure_git(self, self, scenario)
        _assert_push_failure_state(self, self)

    def test_clean_push_failure_skips_handler(self) -> None:
        self._seed_pr_issue()
        self._add_pr()
        scenario = _clean_rebase_scenario(push_result=False)
        in_review = _AwaitingHumanRecorder()

        with patch.object(
            _in_review,
            "_handle_in_review",
            side_effect=in_review,
        ):
            scenario.run(self)
            _dispatch._process_issue(
                self.gh,
                self.spec,
                self.gh._issues[ISSUE],
            )

        self.assertEqual(in_review.observed, [True])
        self.assertEqual(self.gh.posted_pr_comments, [])
        self.assertEqual(self.gh.label_history, [])


if __name__ == "__main__":
    unittest.main()
