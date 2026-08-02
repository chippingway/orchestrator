# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How a window's series rows become one bucket of bands per day."""
from __future__ import annotations

import unittest
from datetime import date

from orchestrator.observability.analytics.query.overview_models import (
    TimeSeriesPoint,
)
from orchestrator.observability.dashboard.charts import usage_bands

_YEAR = 2026

_DAY = date(_YEAR, 5, 1)

_NEXT_DAY = date(_YEAR, 5, 2)

# The rows a usage chart is drawn from are `agent_exit` cells; the event is
# part of the key the read grouped on, not something a band is split by.
_EVENT = "agent_exit"

_INPUT_TOKENS = 1_000

_LATER_INPUT_TOKENS = 2_000

_OUTPUT_TOKENS = 500

_CACHE_READ_TOKENS = 400

_CACHE_WRITE_TOKENS = 200

_COST_USD = 1.5


def _point(day: date, **aggregates: object) -> TimeSeriesPoint:
    """Build one series row, defaulting the key the read grouped on."""
    return TimeSeriesPoint(day=day, event=_EVENT, count=1, **aggregates)


class RollUpTest(unittest.TestCase):
    """Several rows a day, four bands out."""

    def test_rows_sharing_a_day_fold_into_one_bucket(self) -> None:
        # The cache counters are two columns of the one band the chart draws,
        # so they arrive summed rather than as a stack the legend never names.
        daily = usage_bands.roll_up_time_series((
            _point(_DAY, input_tokens=_INPUT_TOKENS, cost_usd=_COST_USD),
            _point(
                _DAY,
                output_tokens=_OUTPUT_TOKENS,
                cache_read_tokens=_CACHE_READ_TOKENS,
                cache_write_tokens=_CACHE_WRITE_TOKENS,
            ),
        ))
        self.assertEqual(tuple(daily), (_DAY,))
        self.assertEqual(daily[_DAY], {
            usage_bands.INPUT_BAND: float(_INPUT_TOKENS),
            usage_bands.OUTPUT_BAND: float(_OUTPUT_TOKENS),
            usage_bands.CACHE_BAND: float(
                _CACHE_READ_TOKENS + _CACHE_WRITE_TOKENS,
            ),
            usage_bands.COST_BAND: _COST_USD,
        })

    def test_each_day_accumulates_into_its_own_bucket(self) -> None:
        daily = usage_bands.roll_up_time_series((
            _point(_DAY, input_tokens=_INPUT_TOKENS),
            _point(_NEXT_DAY, input_tokens=_LATER_INPUT_TOKENS),
        ))
        self.assertEqual(
            [daily[day][usage_bands.INPUT_BAND] for day in (_DAY, _NEXT_DAY)],
            [float(_INPUT_TOKENS), float(_LATER_INPUT_TOKENS)],
        )

    def test_a_null_aggregate_counts_as_zero(self) -> None:
        # A column no row contributed to comes back NULL rather than 0, and a
        # band adding it straight would fail the whole page's load.
        daily = usage_bands.roll_up_time_series((
            _point(
                _DAY,
                cost_usd=None,
                input_tokens=None,
                output_tokens=None,
                cache_read_tokens=None,
                cache_write_tokens=None,
            ),
        ))
        self.assertEqual(daily[_DAY], usage_bands.empty_token_bucket())


class DailyTotalTest(unittest.TestCase):
    """What one day's stack is as tall as."""

    def test_cost_is_left_out_of_the_height(self) -> None:
        # Cost rides the secondary axis under its own range, so a total
        # carrying it would scale the token axis by a number drawn in dollars.
        bucket = {
            usage_bands.INPUT_BAND: float(_INPUT_TOKENS),
            usage_bands.OUTPUT_BAND: float(_OUTPUT_TOKENS),
            usage_bands.CACHE_BAND: float(_CACHE_READ_TOKENS),
            usage_bands.COST_BAND: _COST_USD,
        }
        self.assertEqual(
            usage_bands.daily_token_total(bucket),
            float(_INPUT_TOKENS + _OUTPUT_TOKENS + _CACHE_READ_TOKENS),
        )


if __name__ == "__main__":
    unittest.main()
