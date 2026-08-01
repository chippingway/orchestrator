# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The date window a run of the page reports over.

One owner for the presets the filter bar offers and the arithmetic behind
them, because a preset is only a name for a window this module also builds:
the label, the day count, and the clamp that keeps a span inside the data
extent have to agree, and reading one off a different module than the other is
what would let `7D` mean seven days in the topbar and something else in the
SQL. A window is half-open with a midnight-aligned UTC end one day past the
inclusive end date, which is what makes the read's `ts < end` include events
from that date.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from types import MappingProxyType
from typing import Mapping, Optional

from orchestrator.observability.analytics.query.overview_models import DataExtent


DEFAULT_WINDOW_DAYS = 7
PRESET_RECENT_THREE_DAYS = "3d"
PRESET_RECENT_WEEK = "7d"
PRESET_ALL = "All"
PRESET_CUSTOM = "Custom"
PRESET_OPTIONS = (
    PRESET_RECENT_THREE_DAYS,
    PRESET_RECENT_WEEK,
    PRESET_ALL,
    PRESET_CUSTOM,
)
PRESET_LABELS: Mapping[str, str] = MappingProxyType({
    PRESET_RECENT_THREE_DAYS: "Last 3 days",
    PRESET_RECENT_WEEK: "Last 7 days",
    PRESET_ALL: "All time",
    PRESET_CUSTOM: "Custom range",
})
PRESET_INLINE_LABELS: Mapping[str, str] = MappingProxyType({
    PRESET_RECENT_THREE_DAYS: "3D",
    PRESET_RECENT_WEEK: "7D",
    PRESET_ALL: "All",
})
PRESET_DAYS: Mapping[str, int] = MappingProxyType({
    PRESET_RECENT_THREE_DAYS: 3,
    PRESET_RECENT_WEEK: 7,
})
DEFAULT_PRESET = PRESET_RECENT_WEEK


@dataclass(frozen=True)
class DateWindow:
    start: datetime
    end: datetime


def default_date_range(
    *,
    today: Optional[date] = None,
    days: int = DEFAULT_WINDOW_DAYS,
) -> tuple[date, date]:
    range_end = today or date.today()
    range_start = range_end - timedelta(days=max(days - 1, 0))
    return range_start, range_end


def to_window(start_date: date, end_date: date) -> DateWindow:
    if end_date < start_date:
        start_date, end_date = end_date, start_date
    start_datetime = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_datetime = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    )
    return DateWindow(start=start_datetime, end=end_datetime)


def extent_dates(extent: DataExtent) -> Optional[tuple[date, date]]:
    if extent.min_ts is None or extent.max_ts is None:
        return None
    return extent.min_ts.date(), extent.max_ts.date()


def preset_window(
    preset: str,
    extent: DataExtent,
) -> Optional[DateWindow]:
    bounds = extent_dates(extent)
    if bounds is None:
        return None
    minimum_date, maximum_date = bounds
    if preset == PRESET_ALL:
        return to_window(minimum_date, maximum_date)
    days = PRESET_DAYS.get(preset)
    if days is None:
        return None
    start_date = max(
        maximum_date - timedelta(days=days - 1),
        minimum_date,
    )
    return to_window(start_date, maximum_date)


def previous_window(window: DateWindow) -> DateWindow:
    window_length = window.end - window.start
    return DateWindow(
        start=window.start - window_length,
        end=window.start,
    )
