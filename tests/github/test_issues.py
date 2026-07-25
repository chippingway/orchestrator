# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Non-PR issue filtering and PyGithub issue-query options."""
from __future__ import annotations

import unittest
from datetime import datetime
from typing import Any

from orchestrator import github as _github
from orchestrator.github import issues as _issues

# Facade name -> the `issues` owner attribute it must resolve to.
_FACADE_QUERY_NAMES = (
    ("_iter_new_non_pr_issues", "iter_new_non_pr_issues"),
    ("_issue_query_options", "issue_query_options"),
)

_STATE_OPEN = "open"
_STATE_CLOSED = "closed"
_SINCE = datetime.fromisoformat("2026-07-01T00:00:00+00:00")


def _expected_options(**overrides: Any) -> dict[str, Any]:
    """Return the newest-first open-issue options with overrides applied."""
    expected: dict[str, Any] = {
        "state": _STATE_OPEN,
        "sort": "updated",
        "direction": "desc",
    }
    expected.update(overrides)
    return expected


class _StubIssue:
    """PyGithub-shaped issue; the filter reads only these two attributes."""

    def __init__(self, number: int, *, is_pull_request: bool = False) -> None:
        self.number = number
        self.pull_request = object() if is_pull_request else None


class _StubLabel:
    def __init__(self, name: str) -> None:
        self.name = name


class IterNewNonPrIssuesTest(unittest.TestCase):
    """The poller sees each issue once and never sees a pull request.

    GitHub's issue endpoints return PRs alongside issues, and the open poll and
    the per-label closed sweep overlap, so a shared number set is what keeps a
    stage handler from running twice against the same issue in one tick.
    """

    def test_pull_requests_and_repeats_are_skipped(self) -> None:
        seen_numbers: set[int] = set()
        listed = (
            _StubIssue(1),
            _StubIssue(2, is_pull_request=True),
            _StubIssue(1),
            _StubIssue(3),
        )
        yielded = _issues.iter_new_non_pr_issues(listed, seen_numbers)
        self.assertEqual([issue.number for issue in yielded], [1, 3])
        self.assertEqual(seen_numbers, {1, 3})

    def test_numbers_from_an_earlier_query_skipped(self) -> None:
        seen_numbers = {1}
        yielded = _issues.iter_new_non_pr_issues(
            (_StubIssue(1), _StubIssue(4)),
            seen_numbers,
        )
        self.assertEqual([issue.number for issue in yielded], [4])
        self.assertEqual(seen_numbers, {1, 4})


class IssueQueryOptionsTest(unittest.TestCase):
    """Both polls request newest-first pages of the requested issue state."""

    def test_open_query_omits_label_and_since(self) -> None:
        self.assertEqual(
            _issues.issue_query_options(issue_state=_STATE_OPEN, since=None),
            _expected_options(),
        )

    def test_closed_query_carries_label_and_since(self) -> None:
        label = _StubLabel("in_review")
        self.assertEqual(
            _issues.issue_query_options(
                issue_state=_STATE_CLOSED,
                since=_SINCE,
                label=label,
            ),
            _expected_options(
                state=_STATE_CLOSED,
                labels=[label],
                since=_SINCE,
            ),
        )


class QueryFacadeOwnershipTest(unittest.TestCase):
    """The package surface hands back the `issues` owner's own objects.

    A caller reaching a query helper through `orchestrator.github` sees the
    owning module's function, so a monkeypatch on the owner stays observable
    through the facade rather than resolving a divergent copy.
    """

    def test_facade_names_are_owner_re_exports(self) -> None:
        for facade_name, owner_name in _FACADE_QUERY_NAMES:
            with self.subTest(name=facade_name):
                self.assertIs(
                    getattr(_github, facade_name),
                    getattr(_issues, owner_name),
                )


if __name__ == "__main__":
    unittest.main()
