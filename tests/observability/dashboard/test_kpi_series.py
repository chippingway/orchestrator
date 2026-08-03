# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which rows a sparkline is plotted over, and which columns it counts.

The two token reductions are read against a row carrying all four columns and
one whose cache halves arrived as NULL, because that is the shape a run
recorded before those columns existed reaches a tile as -- and a total that
refused it would take the strip down with it.

The series cases are about the day axis rather than the arithmetic: a day the
activity series recorded twice is one point, a day it recorded with no
resolutions still holds its place in all three lines, and a resolution dated
outside those days is not a fourth point on three-point lines.
"""

from __future__ import annotations

import unittest
from datetime import date

from orchestrator.observability.analytics.query.activity_models import (
    ThroughputDayRow,
)
from orchestrator.observability.analytics.query.overview_models import (
    Summary,
    TimeSeriesPoint,
)
from orchestrator.observability.dashboard import kpi_series
from tests.observability.dashboard.dashboard_test_support import (
    MAY01,
    MAY02,
    MAY03,
)


_EVENT = "agent_exit"

# One order of magnitude per token column, so a reduction dropping any single
# one of the four is off by a distinguishable amount.
_INPUT = 1

_OUTPUT = 20

_CACHE_READ = 300

_CACHE_WRITE = 4_000

_ALL_COLUMNS = _INPUT + _OUTPUT + _CACHE_READ + _CACHE_WRITE

_UNCACHED_COLUMNS = _INPUT + _OUTPUT

_FIRST_DAY_COST = 1.5

_SECOND_DAY_COST = 0.25

_RESOLVED = 2

_REJECTED = 3


def _point(day: date, cost: float, **tokens) -> TimeSeriesPoint:
    """One activity cell, carrying only the token columns it is given."""
    return TimeSeriesPoint(
        day=day, event=_EVENT, count=1, cost_usd=cost, **tokens,
    )


class TokenTotalTest(unittest.TestCase):
    """Every token column a tile and its sparkline are counted over."""

    def test_a_window_totals_all_four_columns(self) -> None:
        window = Summary(
            total_input_tokens=_INPUT,
            total_output_tokens=_OUTPUT,
            total_cache_read_tokens=_CACHE_READ,
            total_cache_write_tokens=_CACHE_WRITE,
        )
        self.assertEqual(kpi_series.summary_total_tokens(window), _ALL_COLUMNS)

    def test_a_point_totals_all_four_columns(self) -> None:
        point = _point(
            MAY01,
            _FIRST_DAY_COST,
            input_tokens=_INPUT,
            output_tokens=_OUTPUT,
            cache_read_tokens=_CACHE_READ,
            cache_write_tokens=_CACHE_WRITE,
        )
        self.assertEqual(
            kpi_series.time_series_total_tokens(point), float(_ALL_COLUMNS),
        )

    def test_an_unrecorded_column_counts_as_zero(self) -> None:
        # A run recorded before the cache columns existed reaches both
        # reductions with them NULL, and the tile it feeds is the window's
        # headline: refusing the row would take the whole strip down.
        point = _point(
            MAY01,
            _FIRST_DAY_COST,
            input_tokens=_INPUT,
            output_tokens=_OUTPUT,
            cache_read_tokens=None,
            cache_write_tokens=None,
        )
        self.assertEqual(
            kpi_series.time_series_total_tokens(point),
            float(_UNCACHED_COLUMNS),
        )
        self.assertEqual(
            kpi_series.summary_total_tokens(
                Summary(
                    total_input_tokens=_INPUT,
                    total_output_tokens=_OUTPUT,
                    total_cache_read_tokens=None,
                    total_cache_write_tokens=None,
                ),
            ),
            _UNCACHED_COLUMNS,
        )


class ThroughputTotalsTest(unittest.TestCase):
    """The pair the reliability tiles beneath the strip are also reported by."""

    def test_both_counts_are_summed_over_the_window(self) -> None:
        rows = (
            ThroughputDayRow(day=MAY01, resolved=_RESOLVED, rejected=0),
            ThroughputDayRow(day=MAY02, resolved=0, rejected=_REJECTED),
        )
        self.assertEqual(
            kpi_series.throughput_totals(rows), (_RESOLVED, _REJECTED),
        )

    def test_a_window_with_no_days_is_zero(self) -> None:
        self.assertEqual(kpi_series.throughput_totals(()), (0, 0))


class DailyKpiSeriesTest(unittest.TestCase):
    """The three lines, and the days they are plotted over."""

    def test_a_day_sums_its_event_rows(self) -> None:
        # The series carries a row per day and event, so the spend and tokens a
        # day is drawn at are filled in over all of them.
        totals = kpi_series.daily_point_totals((
            _point(MAY01, _FIRST_DAY_COST, input_tokens=_INPUT),
            _point(MAY01, _SECOND_DAY_COST, output_tokens=_OUTPUT),
        ))
        day_cost = _FIRST_DAY_COST + _SECOND_DAY_COST
        self.assertEqual(
            totals, {MAY01: [day_cost, float(_UNCACHED_COLUMNS)]},
        )

    def test_the_days_come_off_the_series(self) -> None:
        # A day with runs but no resolutions keeps its place in all three
        # lines, and a resolution dated outside those days is not a fourth
        # point on three-point lines.
        series = kpi_series.daily_kpi_series(
            ts_points=(
                _point(MAY02, _SECOND_DAY_COST, input_tokens=_INPUT),
                _point(MAY01, _FIRST_DAY_COST, output_tokens=_OUTPUT),
            ),
            throughput_rows=(
                ThroughputDayRow(day=MAY01, resolved=_RESOLVED, rejected=0),
                ThroughputDayRow(day=MAY03, resolved=_RESOLVED, rejected=0),
            ),
        )
        self.assertEqual(series.cost, [_FIRST_DAY_COST, _SECOND_DAY_COST])
        self.assertEqual(series.tokens, [float(_OUTPUT), float(_INPUT)])
        self.assertEqual(series.done, [_RESOLVED, 0])

    def test_a_window_with_no_activity_is_empty(self) -> None:
        series = kpi_series.daily_kpi_series(ts_points=(), throughput_rows=())
        self.assertEqual(
            (series.cost, series.tokens, series.done), ([], [], []),
        )


if __name__ == "__main__":
    unittest.main()
