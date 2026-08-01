# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a filtered run set is totalled into for the page's KPI strip."""
from __future__ import annotations

import unittest

from orchestrator.observability.trajectory_viewer import models, summaries
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    TOOL_BASH,
    TOOL_CALL,
    TOOL_EDIT,
    TOOL_RESULT,
    run,
    step,
)


_REPO_A = "a/a"

_REPO_B = "b/b"

_REPORTED = "reported"

_PRICED_COST = 0.8

_ESTIMATED_COST = 0.2


def _priced(cost_usd, cost_source) -> models.RunUsageView:
    """The run summary a record carries once the provider reported one."""
    return models.RunUsageView(cost_usd=cost_usd, cost_source=cost_source)


class HeadlineCountTest(unittest.TestCase):
    """Runs are summed, issues and repositories counted once each."""

    def test_counts_over_a_filtered_set(self) -> None:
        summary = summaries.summarize([
            run(
                issue=1,
                repo=_REPO_A,
                steps=(
                    step(TOOL_CALL, name=TOOL_BASH),
                    step(TOOL_RESULT, tool_id="t"),
                ),
                truncated=True,
            ),
            run(issue=1, repo=_REPO_A, steps=(step(TOOL_CALL, name=TOOL_EDIT),)),
            run(issue=2, repo=_REPO_B),
        ])
        self.assertEqual(summary.total_runs, 3)
        # Two runs share (a/a, 1); (b/b, 2) is the second distinct issue.
        self.assertEqual(summary.distinct_issues, 2)
        self.assertEqual(summary.distinct_repos, 2)
        # Only `tool_call` steps count; the result beside one does not.
        self.assertEqual(summary.total_tool_calls, 2)
        self.assertEqual(summary.truncated_runs, 1)

    def test_an_empty_set_totals_to_zero(self) -> None:
        summary = summaries.summarize([])
        self.assertEqual(
            (
                summary.total_runs,
                summary.distinct_issues,
                summary.distinct_repos,
                summary.total_tool_calls,
                summary.truncated_runs,
                summary.total_cost_usd,
            ),
            (0, 0, 0, 0, 0, float()),
        )


class TotalCostTest(unittest.TestCase):
    """The money totals the runs that recorded some, and only those."""

    def test_only_priced_runs_contribute(self) -> None:
        # A pre-usage record carries no summary at all and an unpriced one
        # carries no figure, so neither adds a spurious zero to the tile.
        summary = summaries.summarize([
            run(issue=1, run_usage=_priced(_PRICED_COST, _REPORTED)),
            run(issue=2, run_usage=_priced(_ESTIMATED_COST, "estimated")),
            run(issue=3),
            run(issue=4, run_usage=_priced(None, "unknown-price")),
        ])
        self.assertAlmostEqual(summary.total_cost_usd, 1.0)


if __name__ == "__main__":
    unittest.main()
