# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory headline-count and total-cost aggregation tests."""

import unittest


from orchestrator import trajectory_reader as tr


_KIND = "kind"


_NAME = "name"


_TOOL_ID = "tool_id"


_COST_USD = "cost_usd"


_COST_SOURCE = "cost_source"


_TOOL_CALL = "tool_call"


_TOOL_RESULT = "tool_result"


_BACKEND_CLAUDE = "claude"


_REPORTED = "reported"


_REPO_A = "a/a"


_REPO_B = "b/b"


_STAGE_IMPLEMENTING = "implementing"


_ROLE_DEVELOPER = "developer"


_TOOL_BASH = "Bash"


_TOOL_EDIT = "Edit"


_TS = "2026-06-20T10:00:00+00:00"


_ISSUE = 42


def _record(**overrides):
    record = {
        "ts": _TS,
        "repo": "acme/widgets",
        "issue": _ISSUE,
        "event": "agent_trajectory",
        "stage": _STAGE_IMPLEMENTING,
        "agent_role": _ROLE_DEVELOPER,
        "backend": _BACKEND_CLAUDE,
        "steps": [],
    }
    record.update(overrides)
    return record


class SummarizeTest(unittest.TestCase):

    def test_counts(self) -> None:
        runs = [
            tr.parse_record(
                _record(issue=1, repo=_REPO_A,
                        steps=[{_KIND: _TOOL_CALL, _NAME: _TOOL_BASH},
                               {_KIND: _TOOL_RESULT, _TOOL_ID: "t"}],
                        truncated=True),
                seq=0,
            ),
            tr.parse_record(
                _record(issue=1, repo=_REPO_A,
                        steps=[{_KIND: _TOOL_CALL, _NAME: _TOOL_EDIT}]),
                seq=1,
            ),
            tr.parse_record(_record(issue=2, repo=_REPO_B), seq=2),
        ]
        summary = tr.summarize(runs)
        self.assertEqual(summary.total_runs, 3)
        # Two runs share (a/a, 1); (b/b, 2) is the third distinct issue.
        self.assertEqual(summary.distinct_issues, 2)
        self.assertEqual(summary.distinct_repos, 2)
        self.assertEqual(summary.total_tool_calls, 2)
        self.assertEqual(summary.truncated_runs, 1)

    def test_empty(self) -> None:
        summary = tr.summarize([])
        self.assertEqual(
            (summary.total_runs, summary.distinct_issues, summary.distinct_repos,
             summary.total_tool_calls, summary.truncated_runs, summary.total_cost_usd),
            (0, 0, 0, 0, 0, float()),
        )

    def test_total_cost_sums_only_priced_runs(self) -> None:
        # The KPI sums the authoritative run cost; a run with no run_usage
        # (pre-usage record) or an unpriced cost (None) contributes nothing
        # rather than a spurious 0.
        runs = [
            tr.parse_record(_record(
                issue=1,
                run_usage={_COST_USD: 0.8, _COST_SOURCE: _REPORTED}),
                seq=0),
            tr.parse_record(_record(
                issue=2,
                run_usage={_COST_USD: 0.2, _COST_SOURCE: "estimated"}),
                seq=1),
            tr.parse_record(_record(issue=3), seq=2),
            tr.parse_record(_record(
                issue=4,
                run_usage={_COST_USD: None, _COST_SOURCE: "unknown-price"}),
                seq=3),
        ]
        self.assertAlmostEqual(tr.summarize(runs).total_cost_usd, 1.0)
