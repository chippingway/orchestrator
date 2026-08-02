# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The days a usage figure spans and the height each of its stacks reaches.

The x-axis is the days the roll-up produced, which is what the backend view
has to be completed against: a day only the per-backend read saw carries no
bucket of its own, and its stack would be drawn past the end of the axis
rather than at its own date. Giving every such day a zeroed bucket is what
keeps the day span, the cost line, and the backend bands indexed by one set of
dates.

The stack totals are what the token axis is scaled to, and the two modes reach
them differently: a per-backend stack is as tall as that day's backends add up
to, while a token-type stack is as tall as the day's three token bands.
Measuring the bands under a backend stack would scale the axis to a series the
figure is not drawing.

Backends are sorted because their order is the legend's order and the color
each is drawn in is picked off its position among them, so an unordered set
would repaint the chart between two loads of the same window.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from orchestrator.observability.dashboard.charts.usage_bands import (
    BACKEND_MODE,
    DailyTokenValues,
    daily_token_total,
    empty_token_bucket,
)


@dataclass(frozen=True)
class UsageChartData:
    """A window's per-day buckets and the days they are drawn along."""

    daily: DailyTokenValues
    days: Sequence[date]


@dataclass(frozen=True)
class UsageAxisRanges:
    """The maxima the token and cost axes are each scaled to."""

    token_top: float
    cost_top: float


def date_axis(days: Sequence[date]) -> list:
    """Return the day span as the x values a trace is added with."""
    return list(days)


def ensure_backend_days(
    daily: DailyTokenValues,
    backend_rows_by_day: DailyTokenValues,
) -> None:
    """Give every day the per-backend read saw a bucket on the axis."""
    for day in backend_rows_by_day:
        daily.setdefault(day, empty_token_bucket())


def backend_names(
    backend_rows_by_day: DailyTokenValues,
) -> list[str]:
    """Return every backend the window holds, in a stable draw order."""
    return sorted(
        {
            backend
            for by_backend in backend_rows_by_day.values()
            for backend in by_backend
        }
    )


def usage_stack_totals(
    days: Sequence[date],
    daily: DailyTokenValues,
    *,
    backend_rows_by_day: Optional[DailyTokenValues],
    mode: str,
) -> list[float]:
    """Return each day's stack height, measured in the drawn mode."""
    if mode == BACKEND_MODE and backend_rows_by_day:
        return [sum(backend_rows_by_day.get(day, {}).values()) for day in days]
    return [daily_token_total(daily[day]) for day in days]
