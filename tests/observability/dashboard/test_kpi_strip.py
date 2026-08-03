# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the four tiles above a page report, off one window's first-wave rows.

The strip is read whole rather than helper by helper, because a tile is only
right while its value, its move against the window before, its sub-line, and
the line drawn under it all describe the same window -- a spend total paired
with a token sparkline is the failure this owner exists to make impossible.

The two readings that are not a division sit beside it: a window that resolved
nothing reports an em dash rather than a cost no issue was charged, and a
window whose review rounds recorded no spend at all reports no rework rather
than failing to draw the tile.

The theme handed in carries the formatting and palette owners' own callables,
because the page hands its own module in and a stand-in rendering would leave
these cases pinning a second set of thresholds instead of which number a tile
reports.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from typing import Sequence

from orchestrator.observability.analytics.query.activity_models import (
    ThroughputDayRow,
)
from orchestrator.observability.analytics.query.cost_models import (
    ReviewRoundBucketRow,
)
from orchestrator.observability.analytics.query.overview_models import (
    Summary,
    TimeSeriesPoint,
)
from orchestrator.observability.dashboard import formatting, kpi_strip, palette
from tests.observability.dashboard.dashboard_test_support import MAY01, MAY07


_EVENT = "agent_exit"

_LABEL_KEY = "label"

_VALUE_KEY = "value"

_SPARK_KEY = "spark"

_DELTA_KEY = "delta"

_SUB_KEY = "sub"

_TOTAL_SPEND = "Total spend"

_TOTAL_TOKENS = "Total tokens"

_COST_PER_RESOLVED = "Cost / resolved issue"

_REWORK_SHARE = "Rework share"

# A window that spent twice what the one before it did, on twice the tokens, so
# both delta pills read the same whole number.
_WINDOW_COST = 12.0

_PREVIOUS_COST = 6.0

_WINDOW_OUTPUT_TOKENS = 20

_WINDOW = Summary(
    total_cost_usd=_WINDOW_COST,
    total_input_tokens=10,
    total_output_tokens=_WINDOW_OUTPUT_TOKENS,
    total_cache_read_tokens=3,
    total_cache_write_tokens=7,
)

_PREVIOUS = Summary(
    total_cost_usd=_PREVIOUS_COST,
    total_input_tokens=5,
    total_output_tokens=5,
    total_cache_read_tokens=5,
    total_cache_write_tokens=5,
)

_WINDOW_TOKENS = 40

_PREVIOUS_TOKENS = 20

_DOUBLED = 1.0

# Two days of activity, the first of them recorded as two event rows.
_FIRST_POINT_COST = 1.5

_LAST_DAY_COST = 4.0

_TS_POINTS = (
    TimeSeriesPoint(
        day=MAY01,
        event=_EVENT,
        count=1,
        cost_usd=_FIRST_POINT_COST,
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=2,
        cache_write_tokens=3,
    ),
    TimeSeriesPoint(
        day=MAY01,
        event=_EVENT,
        count=1,
        cost_usd=0.5,
        input_tokens=1,
        output_tokens=2,
    ),
    TimeSeriesPoint(
        day=MAY07,
        event=_EVENT,
        count=1,
        cost_usd=_LAST_DAY_COST,
        input_tokens=2,
        output_tokens=3,
        cache_read_tokens=1,
        cache_write_tokens=1,
    ),
)

_DAILY_COST = (2.0, _LAST_DAY_COST)

_DAILY_TOKENS = (23.0, 7.0)

_DAILY_DONE = (2, 0)

_THROUGHPUT_ROWS = (
    ThroughputDayRow(day=MAY01, resolved=2, rejected=1),
    ThroughputDayRow(day=MAY07, resolved=0, rejected=1),
)

_RESOLVED = 2

_REJECTED = 2

# Three of the eight review-round dollars were a second pass over work already
# done, which the tile rounds to a whole percent.
_INITIAL_ROUND_COST = 5.0

_REWORK_COST = 3.0

_REVIEW_ROWS = (
    ReviewRoundBucketRow(
        bucket="0", runs=2, total_cost_usd=_INITIAL_ROUND_COST,
    ),
    ReviewRoundBucketRow(bucket="1", runs=1, total_cost_usd=_REWORK_COST),
)

_REVIEW_COST = 8.0

_DAYS_IN_WINDOW = 2


def _theme() -> SimpleNamespace:
    """The theme handle a page hands in, as its formatters and hues."""
    return SimpleNamespace(
        ACCENT=palette.ACCENT,
        TOKEN_TYPE_COLORS=palette.TOKEN_TYPE_COLORS,
        fmt_money=formatting.fmt_money,
        fmt_money_exact=formatting.fmt_money_exact,
        fmt_tokens=formatting.fmt_tokens,
    )


def _inputs(
    review_rows: Sequence[ReviewRoundBucketRow] = _REVIEW_ROWS,
) -> kpi_strip.KpiInputs:
    """One window's first-wave rows, as the page pipeline binds them."""
    return kpi_strip.KpiInputs(
        theme=_theme(),
        summary=_WINDOW,
        prev_summary=_PREVIOUS,
        ts_points=_TS_POINTS,
        throughput_rows=_THROUGHPUT_ROWS,
        review_round_rows=review_rows,
        days_in_window=_DAYS_IN_WINDOW,
    )


def _by_label(inputs: kpi_strip.KpiInputs) -> dict:
    """The strip's entries keyed by the label each tile is drawn under."""
    entries, _, _ = kpi_strip.build_kpi_strip_data(inputs)
    return {entry[_LABEL_KEY]: entry for entry in entries}


class KpiTotalsTest(unittest.TestCase):
    """The scalars a window and the one before it are reduced to."""

    def test_both_windows_are_reduced_together(self) -> None:
        totals = kpi_strip.kpi_totals(_inputs())
        self.assertEqual(totals.tokens, _WINDOW_TOKENS)
        self.assertEqual(totals.previous_tokens, _PREVIOUS_TOKENS)
        self.assertAlmostEqual(totals.cost, _WINDOW.total_cost_usd)
        self.assertAlmostEqual(totals.previous_cost, _PREVIOUS.total_cost_usd)
        self.assertEqual((totals.resolved, totals.rejected), (_RESOLVED, _REJECTED))
        self.assertAlmostEqual(totals.review_cost, _REVIEW_COST)
        self.assertAlmostEqual(totals.rework_cost, _REWORK_COST)


class CostPerResolvedTest(unittest.TestCase):
    """What one resolved issue cost, and what is reported when none were."""

    def test_spend_is_divided_by_the_resolved(self) -> None:
        self.assertEqual(
            _by_label(_inputs())[_COST_PER_RESOLVED][_VALUE_KEY], "$6.00",
        )

    def test_an_unresolved_window_has_no_ratio(self) -> None:
        # Nothing was resolved, so there is no per-issue cost to report: an em
        # dash says so, where a `$0.00` would read as issues resolved for free.
        totals = replace(kpi_strip.kpi_totals(_inputs()), resolved=0)
        self.assertEqual(kpi_strip.cost_per_resolved(totals), "—")


class KpiStripDataTest(unittest.TestCase):
    """The four tiles, and the throughput pair handed back beside them."""

    def test_the_four_tiles_report_the_window(self) -> None:
        entries = _by_label(_inputs())
        self.assertEqual(entries[_TOTAL_SPEND][_VALUE_KEY], "$12")
        self.assertEqual(entries[_TOTAL_TOKENS][_VALUE_KEY], "40")
        self.assertEqual(entries[_TOTAL_SPEND][_DELTA_KEY], _DOUBLED)
        self.assertEqual(entries[_TOTAL_TOKENS][_DELTA_KEY], _DOUBLED)
        self.assertEqual(
            entries[_COST_PER_RESOLVED][_SUB_KEY], "2 resolved · 2 rejected",
        )
        self.assertEqual(entries[_REWORK_SHARE][_VALUE_KEY], "38%")
        self.assertEqual(
            entries[_REWORK_SHARE][_SUB_KEY], "$3 in review rounds >= 1",
        )

    def test_the_sparklines_follow_the_days(self) -> None:
        # Each line is plotted over the days the activity series recorded, so a
        # tile and the line under it describe the same window.
        entries = _by_label(_inputs())
        self.assertEqual(tuple(entries[_TOTAL_SPEND][_SPARK_KEY]), _DAILY_COST)
        self.assertEqual(
            tuple(entries[_TOTAL_TOKENS][_SPARK_KEY]), _DAILY_TOKENS,
        )
        self.assertEqual(
            tuple(entries[_COST_PER_RESOLVED][_SPARK_KEY]), _DAILY_DONE,
        )
        self.assertIsNone(entries[_REWORK_SHARE][_SPARK_KEY])

    def test_the_throughput_pair_comes_back(self) -> None:
        _, resolved, rejected = kpi_strip.build_kpi_strip_data(_inputs())
        self.assertEqual((resolved, rejected), (_RESOLVED, _REJECTED))

    def test_an_unreviewed_window_has_no_rework(self) -> None:
        # No review round recorded any spend, so there is nothing to take a
        # share of and the tile reports none rather than failing to divide.
        entries = _by_label(_inputs(review_rows=()))
        self.assertEqual(entries[_REWORK_SHARE][_VALUE_KEY], "0%")


if __name__ == "__main__":
    unittest.main()
