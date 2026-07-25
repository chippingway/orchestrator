# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Tests for the PR combined check-state surfaces (check-runs 403 scope hint,
partial-read downgrade)."""

from __future__ import annotations

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock

from github import GithubException

from orchestrator.github import GitHubClient

HTTP_FORBIDDEN = 403
HTTP_SERVER_ERROR = 500
MESSAGE_KEY = "message"
GITHUB_LOGGER = "orchestrator.github"
ERROR_LEVEL = "ERROR"
STATE_NONE = "none"
STATE_PENDING = "pending"
STATE_FAILURE = "failure"
STATE_SUCCESS = "success"


class CheckRunsForbiddenSurfacesScopeHintTest(unittest.TestCase):
    """A 403 from the check-runs endpoint almost always means the PAT is
    missing 'Checks: read'. Silently swallowing the exception leaves
    `pr_combined_check_state` at 'none' for Actions-only PRs despite the
    PR being green. Promote the 403 to log.error with a specific message
    naming the scope.
    """

    def test_forbidden_check_runs_log_scope_hint(self) -> None:
        client, pr = _client_with(
            combined_state="",
            combined_total=0,
            check_runs_exc=GithubException(
                HTTP_FORBIDDEN,
                {MESSAGE_KEY: "Resource not accessible"},
                None,
            ),
        )
        log_capture = MagicMock()
        with ExitStack() as stack:
            log_capture.records = stack.enter_context(
                self.assertLogs(GITHUB_LOGGER, level=ERROR_LEVEL),
            )
            self.assertEqual(client.pr_combined_check_state(pr), STATE_NONE)

        joined = "\n".join(log_capture.records.output)
        self.assertIn("403", joined)
        self.assertIn("Checks: read", joined)
        self.assertIn("check_state", joined)

    def test_other_check_error_logs_warning(self) -> None:
        # 404, transient 5xx, etc. are logged at warning level and don't
        # need scope guidance. Avoid noisy ERROR for unrelated failures.
        client, pr = _client_with(
            combined_state="",
            combined_total=0,
            check_runs_exc=GithubException(
                HTTP_SERVER_ERROR,
                {MESSAGE_KEY: "Internal Server Error"},
                None,
            ),
        )
        log_capture = MagicMock()
        with ExitStack() as stack:
            log_capture.records = stack.enter_context(
                self.assertLogs(GITHUB_LOGGER, level="WARNING"),
            )
            client.pr_combined_check_state(pr)

        self._assert_warning_records(log_capture.records)

    def _assert_warning_records(self, captured_logs) -> None:
        warning_only = [record for record in captured_logs.records if record.levelname == "WARNING"]
        self.assertTrue(warning_only, "should log a warning for non-403 errors")
        error_records = [record for record in captured_logs.records if record.levelname == ERROR_LEVEL]
        self.assertEqual(error_records, [])


class CombinedCheckStateNormalizationTest(unittest.TestCase):
    def test_normalizes_combined_statuses(self) -> None:
        from orchestrator.github import _normalize_combined_status

        cases = (
            ("", 0, None),
            (STATE_PENDING, 0, None),
            (STATE_PENDING, 1, STATE_PENDING),
            ("error", 1, STATE_FAILURE),
            (STATE_FAILURE, 1, STATE_FAILURE),
            (STATE_SUCCESS, 1, STATE_SUCCESS),
        )

        for status, total_count, expected in cases:
            with self.subTest(status=status, total_count=total_count):
                combined_status = SimpleNamespace(
                    state=status,
                    total_count=total_count,
                )
                self.assertEqual(
                    _normalize_combined_status(combined_status),
                    expected,
                )

    def test_normalizes_check_run_conclusions(self) -> None:
        from orchestrator.github import _normalize_check_runs

        cases = (
            ((), None),
            ((None, STATE_FAILURE), STATE_PENDING),
            ((STATE_FAILURE,), STATE_FAILURE),
            (("timed_out",), STATE_FAILURE),
            (("action_required",), STATE_FAILURE),
            (("cancelled",), STATE_FAILURE),
            ((STATE_SUCCESS, "neutral", "skipped"), STATE_SUCCESS),
            (("unknown",), STATE_FAILURE),
        )

        for conclusions, expected in cases:
            with self.subTest(conclusions=conclusions):
                check_runs = [SimpleNamespace(conclusion=conclusion) for conclusion in conclusions]
                self.assertEqual(_normalize_check_runs(check_runs), expected)

    def test_folds_surface_states_by_priority(self) -> None:
        from orchestrator.github import _fold_check_states

        cases = (
            ((), False, STATE_NONE),
            ((None, None), True, STATE_NONE),
            ((STATE_SUCCESS, None), True, STATE_PENDING),
            ((STATE_SUCCESS, STATE_PENDING), False, STATE_PENDING),
            ((STATE_FAILURE, STATE_PENDING), False, STATE_FAILURE),
            ((STATE_SUCCESS, STATE_SUCCESS), False, STATE_SUCCESS),
            (("unknown",), False, STATE_SUCCESS),
        )

        for states, read_failed, expected in cases:
            with self.subTest(states=states, read_failed=read_failed):
                self.assertEqual(
                    _fold_check_states(states, read_failed=read_failed),
                    expected,
                )


def _client_with(*, combined_state, combined_total, check_runs_exc):
    client = GitHubClient.__new__(GitHubClient)
    client.repo = MagicMock()
    commit_obj = MagicMock()
    commit_obj.get_combined_status.return_value = MagicMock(
        state=combined_state,
        total_count=combined_total,
    )
    commit_obj.get_check_runs.side_effect = check_runs_exc
    client.repo.get_commit.return_value = commit_obj
    pr = MagicMock()
    pr.head.sha = "deadbeef"
    return client, pr


class PartialCheckReadFailsClosedTest(unittest.TestCase):
    """A read failure on one checks surface must NOT be masked by a
    'success' from the other surface. Otherwise a single green
    commit-status context plus failing or pending GitHub Actions check-runs
    that the PAT cannot read (403 from a missing 'Checks: read' scope, or a
    transient 5xx) would be reported as 'success' so a caller could trust
    the head as green over the unread failing checks.
    """

    def test_success_plus_forbidden_returns_pending(self) -> None:
        # The dangerous case: legacy commit-status says 'success' but the
        # PAT cannot read check-runs. Without the partial-read guard, a
        # caller would trust the head as green over failing/pending
        # Actions runs.
        client, pr = _client_with(
            combined_state=STATE_SUCCESS,
            combined_total=1,
            check_runs_exc=GithubException(
                HTTP_FORBIDDEN,
                {MESSAGE_KEY: "Resource not accessible"},
                None,
            ),
        )
        with self.assertLogs(GITHUB_LOGGER, level=ERROR_LEVEL):
            state = client.pr_combined_check_state(pr)
        self.assertEqual(
            state,
            STATE_PENDING,
            "partial read with combined='success' must downgrade to "
            "'pending' so callers do not trust the head as green on half "
            "the picture",
        )

    def test_server_error_downgrades_success(self) -> None:
        # A transient 5xx on check-runs has the same downgrade rule -- the
        # next tick may succeed and resolve to a real verdict, but until
        # then we cannot report success.
        client, pr = _client_with(
            combined_state=STATE_SUCCESS,
            combined_total=1,
            check_runs_exc=GithubException(
                HTTP_SERVER_ERROR,
                {MESSAGE_KEY: "Internal Server Error"},
                None,
            ),
        )
        with self.assertLogs(GITHUB_LOGGER, level="WARNING"):
            state = client.pr_combined_check_state(pr)
        self.assertEqual(state, STATE_PENDING)

    def test_no_combined_plus_forbidden_returns_none(self) -> None:
        # Edge case: combined-status returned no usable signal AND
        # check-runs raised. We have NO signal at all; preserve the
        # existing 'none' return so the workflow's failed_checks branch
        # parks awaiting_human (visible to the operator) instead of
        # silently waiting forever on 'pending'.
        client, pr = _client_with(
            combined_state="",
            combined_total=0,
            check_runs_exc=GithubException(
                HTTP_FORBIDDEN,
                {MESSAGE_KEY: "Resource not accessible"},
                None,
            ),
        )
        with self.assertLogs(GITHUB_LOGGER, level=ERROR_LEVEL):
            state = client.pr_combined_check_state(pr)
        self.assertEqual(
            state,
            STATE_NONE,
            "no signal on either surface must keep returning 'none' so "
            "the workflow parks awaiting_human instead of pending forever",
        )
