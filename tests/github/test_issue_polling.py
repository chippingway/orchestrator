# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The shared number set every query a poll takes is filtered through."""
from __future__ import annotations

import unittest

from orchestrator.github import issue_polling as _issue_polling


class _StubIssue:
    """PyGithub-shaped issue; the filter reads only these two attributes."""

    def __init__(self, number: int, *, is_pull_request: bool = False) -> None:
        self.number = number
        self.pull_request = object() if is_pull_request else None


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
        yielded = _issue_polling.iter_new_non_pr_issues(listed, seen_numbers)
        self.assertEqual([issue.number for issue in yielded], [1, 3])
        self.assertEqual(seen_numbers, {1, 3})

    def test_numbers_from_an_earlier_query_skipped(self) -> None:
        seen_numbers = {1}
        yielded = _issue_polling.iter_new_non_pr_issues(
            (_StubIssue(1), _StubIssue(4)),
            seen_numbers,
        )
        self.assertEqual([issue.number for issue in yielded], [4])
        self.assertEqual(seen_numbers, {1, 4})


if __name__ == "__main__":
    unittest.main()
