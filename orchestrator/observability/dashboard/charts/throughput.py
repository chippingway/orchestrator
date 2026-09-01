# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The per-day strip a window's resolved-issue rhythm is read off.

One bar per day, as tall as the issues that reached a resolved stage that
day. The read only returns days that carried such a row at all, so a Tuesday
nobody finished anything on arrives absent rather than as a zero, and a strip
drawn straight off the rows would run three busy days together and read as a
week of steady output.

Given the window's inclusive bounds, the days between them are the days
drawn, and the ones no row named are drawn at zero -- a continuous baseline
is what makes a quiet day legible as a quiet day instead of as an interval
the axis skipped. Without both bounds the rows are the calendar, in day
order, so a caller with no window to hand still gets a strip.

The shared placeholder is therefore only reachable without bounds: with them
a window always has days, and a range nothing resolved in is an all-zero
baseline rather than a sentence. Either way the strip's pinned height travels
with the figure, because the panel shares the narrow reliability column with
the tiles above it and Plotly's own default would stand it half again as
tall as they do.

Plotly lives in the optional `dashboard` dependency group, so it is imported
inside the call that builds the figure: importing this owner has to work in
the default install, which does not carry it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Sequence

from orchestrator.observability.analytics.query.activity_models import (
    ThroughputDayRow,
)
from orchestrator.observability.dashboard.charts.primitives import empty_figure
from orchestrator.observability.dashboard.layout import base_layout
from orchestrator.observability.dashboard.palette import SUCCESS

if TYPE_CHECKING:
    from plotly import graph_objects as go

# What the strip is pinned to (px): the panel sits in the narrow reliability
# column beneath the tiles, which Plotly's 450px default would dwarf.
THROUGHPUT_CHART_HEIGHT = 150


@dataclass(frozen=True)
class ThroughputSeries:
    """The days a strip draws a bar for, and the count each bar carries."""

    days: Sequence[date]
    resolved: Sequence[int]


def calendar_days(window_start: date, window_end: date) -> list[date]:
    """Every day from one bound to the other, both ends included."""
    days: list[date] = []
    current = window_start
    while current <= window_end:
        days.append(current)
        current = current + timedelta(days=1)
    return days


def throughput_series(
    rows: Sequence[ThroughputDayRow],
    window_start: date | None,
    window_end: date | None,
) -> ThroughputSeries:
    """The rows laid over the window's calendar, zero where none landed."""
    resolved_by_day = {row.day: int(row.resolved or 0) for row in rows}
    if window_start is not None and window_end is not None:
        days = calendar_days(window_start, window_end)
    else:
        days = sorted(resolved_by_day)
    return ThroughputSeries(
        days=days,
        resolved=[resolved_by_day.get(day, 0) for day in days],
    )


def done_per_day_bars(
    rows: Sequence[ThroughputDayRow],
    *,
    window_start: date | None = None,
    window_end: date | None = None,
    title: str | None = None,
) -> go.Figure:
    """Issues-resolved-per-day bars for the reliability panel.

    `window_start` / `window_end` are inclusive `date`s. Passing both draws
    every day between them, so the days nothing resolved on stand as zero
    bars on a continuous baseline instead of dropping off the axis. Passing
    neither draws only the days `rows` names.
    """
    from plotly import graph_objects as go

    series = throughput_series(rows, window_start, window_end)
    if not series.days:
        return empty_figure(
            "No resolved issues in the current window.",
            height=THROUGHPUT_CHART_HEIGHT,
        )
    fig = go.Figure(
        go.Bar(
            x=series.days,
            y=series.resolved,
            marker_color=SUCCESS,
            hovertemplate="%{x}: %{y} resolved<extra></extra>",
        )
    )
    layout = base_layout(title=title)
    top_margin = layout["margin"]["t"]
    layout["margin"] = {"l": 40, "r": 16, "t": top_margin, "b": 32}
    layout["yaxis"] = {
        **layout.get("yaxis", {}),
        "title": {"text": "resolved"},
    }
    layout["height"] = THROUGHPUT_CHART_HEIGHT
    fig.update_layout(**layout)
    return fig
