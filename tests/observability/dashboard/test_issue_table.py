# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The panel a window's costliest issues are ranked into.

The cases name what the panel decides rather than what the shared table draws:
the six columns an operator reads across, the bar each row's spend is sized
against the costliest row by, the tone a review round crosses into once an
issue has been round-tripped past what the flow expects, and the pill that
answers whether the issue needs looking at rather than counting the runs it
took. An empty window is here too, because the panel is what a page opened to
find out that a window is empty renders.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from orchestrator.observability.analytics.query.run_models import (
    IssueSummaryRow,
)
from orchestrator.observability.dashboard import issue_table

_YEAR = 2026

_FIRST_SEEN = datetime(_YEAR, 5, 1, tzinfo=timezone.utc)

_LAST_SEEN = datetime(_YEAR, 5, 2, tzinfo=timezone.utc)

_REPO = "acme/orchestrator"

_OTHER_REPO = "acme/tooling"

_STAGE = "implementing"

_AGENT_EXITS = 4

# The costliest row in a case and the one drawn at half its width, so the two
# widths are readable off the rendered markup.
_TOP_COST = 10.0

_HALF_COST = 5.0

_HALF_COST_TEXT = "$5.00"

_HALF_PCT = 50

_FULL_WIDTH = "width:100.0%"

_HALF_WIDTH = "width:50.0%"

_EMPTY_WIDTH = "width:0.0%"

# The round an issue is toned at, and the one below it that stays plain.
_WARN_ROUND = 3

_PLAIN_ROUND = 2

_FAILED_RUNS = 3


@dataclass(frozen=True)
class _IssueCase:
    repo: str = _REPO
    issue: int = 1
    cost: float | None = _TOP_COST
    failed: int = 0
    max_round: int | None = None
    max_retry: int | None = None


def _row(case: _IssueCase) -> IssueSummaryRow:
    """One read row, carrying only the fields a cell is drawn from."""
    return IssueSummaryRow(
        repo=case.repo,
        issue=case.issue,
        event_count=10,
        first_seen=_FIRST_SEEN,
        last_seen=_LAST_SEEN,
        latest_stage=_STAGE,
        agent_exits=_AGENT_EXITS,
        total_cost_usd=case.cost,
        total_input_tokens=0,
        total_output_tokens=0,
        max_review_round=case.max_round,
        failed_agent_runs=case.failed,
        max_retry_count=case.max_retry,
    )


def _rendered(*cases: _IssueCase) -> str:
    """The panel those issues are ranked into."""
    return issue_table.issues_table_html([_row(case) for case in cases])


class IssuesTableHtmlTest(unittest.TestCase):
    """What the panel reports across its six columns, and how it is sized."""

    def test_every_column_is_headed(self) -> None:
        rendered = _rendered(_IssueCase())
        for header, _aligned in issue_table.ISSUES_TABLE_COLUMNS:
            with self.subTest(header=header):
                self.assertIn(f">{header}<", rendered)

    def test_a_bar_is_a_share_of_the_costliest_row(self) -> None:
        rendered = _rendered(
            _IssueCase(cost=_TOP_COST),
            _IssueCase(repo=_OTHER_REPO, issue=2, cost=_HALF_COST),
        )
        self.assertIn(_FULL_WIDTH, rendered)
        self.assertIn(_HALF_WIDTH, rendered)

    def test_a_window_nobody_priced_draws_empty_bars(self) -> None:
        # There is no costliest row to be a share of, so the panel divides by
        # one rather than raising on the page opened to find that out.
        rendered = _rendered(_IssueCase(cost=None))
        self.assertIn(_EMPTY_WIDTH, rendered)
        self.assertIn("—", rendered)

    def test_an_empty_window_is_headers_and_no_rows(self) -> None:
        rendered = _rendered()
        self.assertIn("<tbody></tbody>", rendered)
        self.assertIn(">Issue<", rendered)

    def test_the_repository_is_named_and_escaped(self) -> None:
        rendered = _rendered(_IssueCase(repo="acme/we<b>ird"))
        self.assertIn("we&lt;b&gt;ird", rendered)
        self.assertNotIn("we<b>ird", rendered)


class IssueRowReadingsTest(unittest.TestCase):
    """The two readings a row's rework and run health are drawn from."""

    def test_the_status_pill_answers_clean_or_a_count(self) -> None:
        clean = issue_table.issue_status_pill(0)
        failing = issue_table.issue_status_pill(_FAILED_RUNS)
        self.assertIn('class="orch-pill ok"', clean)
        self.assertIn(">clean<", clean)
        self.assertIn('class="orch-pill bad"', failing)
        self.assertIn(f">{_FAILED_RUNS} fail<", failing)

    def test_a_round_is_toned_from_the_third_pass_on(self) -> None:
        toned = issue_table.review_round_html(_WARN_ROUND)
        self.assertEqual(
            toned, f'<span class="orch-badge-warn">{_WARN_ROUND}</span>',
        )
        self.assertEqual(
            issue_table.review_round_html(_PLAIN_ROUND), str(_PLAIN_ROUND),
        )

    def test_a_row_reduces_to_what_its_cells_read(self) -> None:
        # A read answers an issue that never reached review or a retry with a
        # null, and both columns are right-aligned numerals.
        view = issue_table.issue_row_view(
            _row(_IssueCase(cost=_HALF_COST)), _TOP_COST,
        )
        self.assertEqual(view.short_repo, "orchestrator")
        self.assertEqual(view.cost_text, _HALF_COST_TEXT)
        self.assertEqual(view.bar_pct, _HALF_PCT)
        self.assertEqual(view.review_rounds, 0)
        self.assertEqual(view.retries, 0)


if __name__ == "__main__":
    unittest.main()
