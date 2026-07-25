# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Check-surface normalization, folding, and reads on the `checks` owner."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from github import GithubException

from orchestrator.github import checks as _checks
from orchestrator.github.client import GitHubClient

_HEAD_SHA = "deadbeef"
_LOGGER = "orchestrator.github"
_ERROR_LEVEL = "ERROR"
_WARNING_LEVEL = "WARNING"
_STATE_NONE = "none"
_STATE_PENDING = "pending"
_STATE_FAILURE = "failure"
_STATE_SUCCESS = "success"
_HTTP_FORBIDDEN = 403
_HTTP_SERVER_ERROR = 500


def _combined(state: str, total_count: int) -> SimpleNamespace:
    return SimpleNamespace(state=state, total_count=total_count)


def _error(status: int) -> GithubException:
    return GithubException(status, {"message": "unreadable"}, None)


# (combined status, total contexts) as GitHub serves it -> the shared state
# model. A `pending` with no contexts is GitHub's "nothing posted here" rather
# than a real wait, and the legacy `error` state is a failure by another name.
_COMBINED_STATUS_CASES = (
    (_combined("", 0), None),
    (_combined(_STATE_PENDING, 0), None),
    (_combined(_STATE_PENDING, 1), _STATE_PENDING),
    (_combined("error", 1), _STATE_FAILURE),
    (_combined(_STATE_FAILURE, 1), _STATE_FAILURE),
    (_combined(_STATE_SUCCESS, 1), _STATE_SUCCESS),
)

# Head check-run conclusions -> the shared state model. An unfinished run wins
# over a finished failure because the verdict is not finished either, and an
# unrecognized conclusion counts as a failure so it is never read as green.
_CHECK_RUN_CASES = (
    ((), None),
    ((None, _STATE_FAILURE), _STATE_PENDING),
    ((_STATE_FAILURE,), _STATE_FAILURE),
    (("timed_out",), _STATE_FAILURE),
    (("action_required",), _STATE_FAILURE),
    (("cancelled",), _STATE_FAILURE),
    ((_STATE_SUCCESS, "neutral", "skipped"), _STATE_SUCCESS),
    (("unknown",), _STATE_FAILURE),
)

# (per-surface states, whether a surface read failed) -> the folded state.
_FOLD_CASES = (
    ((), False, _STATE_NONE),
    ((None, None), True, _STATE_NONE),
    ((_STATE_SUCCESS, None), True, _STATE_PENDING),
    ((_STATE_SUCCESS, _STATE_PENDING), False, _STATE_PENDING),
    ((_STATE_FAILURE, _STATE_PENDING), False, _STATE_FAILURE),
    ((_STATE_SUCCESS, _STATE_SUCCESS), False, _STATE_SUCCESS),
)

# One surface reports green while the other cannot be read at all, whichever
# surface that is and whether the read failed on permissions or transiently.
_PARTIAL_READ_CASES = (
    ("check-runs forbidden", _combined(_STATE_SUCCESS, 1), _error(_HTTP_FORBIDDEN)),
    ("check-runs unavailable", _combined(_STATE_SUCCESS, 1), _error(_HTTP_SERVER_ERROR)),
    ("status unavailable", _error(_HTTP_SERVER_ERROR), (_STATE_SUCCESS,)),
)


def _surface(outcome: Any) -> MagicMock:
    """Mock one commit surface that either answers or raises."""
    if isinstance(outcome, GithubException):
        return MagicMock(side_effect=outcome)
    return MagicMock(return_value=outcome)


def _client_and_pr(combined: Any, check_runs: Any) -> tuple[GitHubClient, Any]:
    """Client whose head-commit surfaces answer with values or raise."""
    if isinstance(check_runs, tuple):
        check_runs = [
            SimpleNamespace(conclusion=conclusion)
            for conclusion in check_runs
        ]
    # Bypass the networked __init__; the check reads touch only `self.repo`.
    client = GitHubClient.__new__(GitHubClient)
    client.repo = MagicMock()
    client.repo.get_commit.return_value = MagicMock(
        get_combined_status=_surface(combined),
        get_check_runs=_surface(check_runs),
    )
    pull_request = MagicMock()
    pull_request.head.sha = _HEAD_SHA
    return client, pull_request


class CheckSurfaceNormalizationTest(unittest.TestCase):
    """Both raw GitHub surfaces reduce to one small state vocabulary."""

    def test_normalizes_combined_statuses(self) -> None:
        for combined_status, expected in _COMBINED_STATUS_CASES:
            with self.subTest(status=combined_status.state):
                self.assertEqual(
                    _checks.normalize_combined_status(combined_status),
                    expected,
                )

    def test_normalizes_check_run_conclusions(self) -> None:
        for conclusions, expected in _CHECK_RUN_CASES:
            with self.subTest(conclusions=conclusions):
                check_runs = [
                    SimpleNamespace(conclusion=conclusion)
                    for conclusion in conclusions
                ]
                self.assertEqual(
                    _checks.normalize_check_runs(check_runs),
                    expected,
                )

    def test_folds_surfaces_failure_before_pending(self) -> None:
        # An unread surface beside a real state contributes a `pending` so the
        # fold never reports a verdict drawn from half the picture.
        for states, read_failed, expected in _FOLD_CASES:
            with self.subTest(states=states, read_failed=read_failed):
                self.assertEqual(
                    _checks.fold_check_states(states, read_failed=read_failed),
                    expected,
                )


class CombinedCheckStateTest(unittest.TestCase):
    """`pr_combined_check_state` folds both surfaces read at the PR head."""

    def test_green_surfaces_read_the_head_sha(self) -> None:
        client, pull_request = _client_and_pr(
            _combined(_STATE_SUCCESS, 1),
            (_STATE_SUCCESS,),
        )

        self.assertEqual(
            client.pr_combined_check_state(pull_request),
            _STATE_SUCCESS,
        )
        read_shas = [
            commit_call.args
            for commit_call in client.repo.get_commit.call_args_list
        ]
        self.assertEqual(read_shas, [(_HEAD_SHA,), (_HEAD_SHA,)])

    def test_unreadable_surface_downgrades_success(self) -> None:
        # Reporting `success` off the readable surface alone would let a caller
        # trust the head as green over failing or pending checks it never saw.
        for case, combined, check_runs in _PARTIAL_READ_CASES:
            with self.subTest(case=case):
                client, pull_request = _client_and_pr(combined, check_runs)
                with self.assertLogs(_LOGGER, level=_WARNING_LEVEL):
                    self.assertEqual(
                        client.pr_combined_check_state(pull_request),
                        _STATE_PENDING,
                    )

    def test_forbidden_read_is_none_and_names_scope(self) -> None:
        # A 403 here is almost always a PAT without 'Checks: read', so the
        # diagnostic names the scope. With neither surface readable the fold
        # keeps `none`, which parks the issue awaiting_human rather than
        # waiting forever on a `pending` that no verdict will ever resolve.
        client, pull_request = _client_and_pr(
            _combined("", 0),
            _error(_HTTP_FORBIDDEN),
        )

        with self.assertLogs(_LOGGER, level=_ERROR_LEVEL) as captured:
            state = client.pr_combined_check_state(pull_request)
            diagnostic = "\n".join(captured.output)

        self.assertEqual(state, _STATE_NONE)
        self.assertIn("403", diagnostic)
        self.assertIn("Checks: read", diagnostic)
        self.assertIn("check_state", diagnostic)

    def test_other_check_run_failure_stays_a_warning(self) -> None:
        # A 404 or transient 5xx needs no scope guidance, and raising it to
        # ERROR would train the operator to ignore the one that matters.
        client, pull_request = _client_and_pr(
            _combined("", 0),
            _error(_HTTP_SERVER_ERROR),
        )

        with self.assertLogs(_LOGGER, level=_WARNING_LEVEL) as captured:
            client.pr_combined_check_state(pull_request)
            levels = {record.levelname for record in captured.records}

        self.assertEqual(levels, {_WARNING_LEVEL})


class ChecksOwnershipTest(unittest.TestCase):
    """The composed client reads its check surface from the owner.

    `pr_combined_check_state` reaches the client through the owner's mixin, so a
    monkeypatch on the owner stays observable rather than hitting a copy.
    """

    def test_client_inherits_the_checks_mixin_owner(self) -> None:
        self.assertIn(_checks.GitHubChecksMixin, GitHubClient.__mro__)


if __name__ == "__main__":
    unittest.main()
