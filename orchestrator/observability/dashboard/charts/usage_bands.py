# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a day of usage is counted into before any of it is drawn.

The series a usage figure is built from arrives as one row per `(day, event)`,
so several rows land on the same date and the two cache counters are two
columns of one band. The roll-up here is the single place those rows become a
day: every point is added into the four bands its day already carries, with
cache read and cache write summed into one because the chart draws a single
Cache band and a stack that kept them apart would say twice what the legend
does.

The band names are declared here rather than spelled at each call site,
because the same four keys are the accumulator's slots, the stack's trace
order, and the input to the axis maximum -- a second spelling of "cache" would
roll up into a band no trace reads. `BACKEND_MODE` sits with them because the
mode a page switches the stack with is compared in more than one owner.

The daily total is tokens only. Cost rides the figure's secondary axis under
its own range, so folding it into the stack's height would scale the token
axis by a number drawn in dollars.
"""
from __future__ import annotations

from datetime import date
from typing import Sequence

from orchestrator.observability.analytics.query.overview_models import (
    TimeSeriesPoint,
)

INPUT_BAND = "input"
OUTPUT_BAND = "output"
CACHE_BAND = "cache"
COST_BAND = "cost"
BACKEND_MODE = "backend"

DailyTokenValues = dict[date, dict[str, float]]


def empty_token_bucket() -> dict[str, float]:
    """Return a fresh zeroed token and cost accumulator."""
    return {
        INPUT_BAND: float(),
        OUTPUT_BAND: float(),
        CACHE_BAND: float(),
        COST_BAND: float(),
    }


def roll_up_time_series(
    points: Sequence[TimeSeriesPoint],
) -> DailyTokenValues:
    """Fold the series' rows into one bucket per day."""
    daily: DailyTokenValues = {}
    for point in points:
        bucket = daily.setdefault(point.day, empty_token_bucket())
        bucket[INPUT_BAND] += float(point.input_tokens or 0)
        bucket[OUTPUT_BAND] += float(point.output_tokens or 0)
        bucket[CACHE_BAND] += float(
            (point.cache_read_tokens or 0) + (point.cache_write_tokens or 0)
        )
        bucket[COST_BAND] += float(point.cost_usd or 0)
    return daily


def daily_token_total(bucket: dict[str, float]) -> float:
    """Add up a day's token bands, leaving its cost out of the height."""
    return sum(
        bucket[token_type]
        for token_type in (INPUT_BAND, OUTPUT_BAND, CACHE_BAND)
    )
