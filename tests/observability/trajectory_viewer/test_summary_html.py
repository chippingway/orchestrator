# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The banner and the five tiles a whole read is summarized in."""
from __future__ import annotations

import unittest

from orchestrator.observability.trajectory_viewer import summaries, summary_html

_TOTAL_RUNS = 10

_SHOWN_RUNS = 3

_TOOL_CALLS = 11

_TOTAL_COST = 12.5


class CardHeaderHtmlTest(unittest.TestCase):
    """A card's title line is caller text, so it is escaped."""

    def test_title_and_sub_escaped(self) -> None:
        rendered = summary_html.card_header_html("Title <b>", "Sub & more")
        self.assertIn("orch-card-title", rendered)
        self.assertIn("Title &lt;b&gt;", rendered)
        self.assertIn("Sub &amp; more", rendered)


class TopbarHtmlTest(unittest.TestCase):
    """The banner reports the whole file and the narrowing over it."""

    def test_carries_title_and_in_view_pill(self) -> None:
        rendered = summary_html.topbar_html(_TOTAL_RUNS, _SHOWN_RUNS)
        self.assertIn("orch-topbar", rendered)
        self.assertIn("Orchestrator Trajectories", rendered)
        self.assertIn("10 recorded", rendered)
        self.assertIn("3 / 10", rendered)


class KpiStripHtmlTest(unittest.TestCase):
    """The five tiles, their labels, and the two figures with a footnote."""

    def test_tiles_truncated_foot_and_cost(self) -> None:
        summary = summaries.TrajectorySummary(
            total_runs=5,
            distinct_issues=3,
            distinct_repos=2,
            total_tool_calls=_TOOL_CALLS,
            truncated_runs=1,
            total_cost_usd=_TOTAL_COST,
        )
        rendered = summary_html.kpi_strip_html(summary)
        self.assertIn("orch-kpis", rendered)
        for label in ("Runs", "Issues", "Repos", "Tool calls", "Total cost"):
            with self.subTest(label=label):
                self.assertIn(f">{label}</span>", rendered)
        self.assertIn("1 truncated", rendered)
        # Exact cents even above $10 -- the compact `fmt_money` would read
        # `$12`, dropping the authoritative figure's cents.
        self.assertIn(">$12.50</div>", rendered)

    def test_no_truncated_reads_none_and_zero_cost(self) -> None:
        rendered = summary_html.kpi_strip_html(
            summaries.TrajectorySummary(total_runs=2),
        )
        self.assertIn("none truncated", rendered)
        self.assertIn(">$0.00</div>", rendered)


if __name__ == "__main__":
    unittest.main()
