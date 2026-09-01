# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a usage figure is drawn as: its stacked bands and its cost line.

A window is shaped before any of it is drawn, and that is also where a window
holding nothing is answered: a series with no rows and no per-backend rows has
no chart at all, and the caller draws the shared placeholder rather than a
figure whose axes are labelled for data that is not behind them. The backend
view completes its day span first, because the two reads are windowed alike but
grouped differently and a day only one of them saw still belongs on the axis.

The stack is one mode or the other, never both: per backend when the page asked
for that and the per-backend read came back with rows, and the three token
bands otherwise. A backend's color is picked off its position among the sorted
backends, so the band an operator followed last week is the same hue this week,
while a token band takes the fixed hue its name is spelled in.

Cost is the one trace that leaves the token axis. It is added against the
secondary axis so it can be labelled in dollars, and drawn as a line with
markers rather than a band so it reads as an overlay over the stack instead of
another layer of it.

Plotly lives in the optional `dashboard` dependency group, so it is imported
inside the calls that add a trace: importing this owner has to work in the
default install, which does not carry it.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Sequence

from orchestrator.observability.analytics.query.overview_models import (
    TimeSeriesPoint,
)
from orchestrator.observability.dashboard.charts.usage_bands import (
    BACKEND_MODE,
    CACHE_BAND,
    COST_BAND,
    DailyTokenValues,
    INPUT_BAND,
    OUTPUT_BAND,
    roll_up_time_series,
)
from orchestrator.observability.dashboard.charts.usage_series import (
    UsageChartData,
    backend_names,
    date_axis,
    ensure_backend_days,
)
from orchestrator.observability.dashboard.palette import (
    BACKEND_COLORS,
    INK,
    TOKEN_TYPE_COLORS,
    color_for,
)

if TYPE_CHECKING:
    from plotly import graph_objects as go

_COLOR_KEY = "color"


def add_token_stack_trace(
    figure: go.Figure,
    *,
    days: Sequence[date],
    token_series: Sequence[float],
    name: str,
    color: str,
) -> None:
    """Add one band of the token stack, filled in the color given."""
    from plotly import graph_objects as go

    figure.add_trace(
        go.Scatter(
            x=date_axis(days),
            y=list(token_series),
            name=name,
            mode="lines",
            stackgroup="tokens",
            line={"width": 0.5, _COLOR_KEY: color},
            fillcolor=color,
            hovertemplate=f"%{{x}}<br>{name}: %{{y:,}} tokens<extra></extra>",
        )
    )


def prepare_usage_data(
    points: Sequence[TimeSeriesPoint],
    backend_rows_by_day: DailyTokenValues | None,
    mode: str,
) -> UsageChartData | None:
    """Shape the window into a figure's days, or nothing to draw."""
    if not points and not backend_rows_by_day:
        return None
    daily = roll_up_time_series(points)
    if mode == BACKEND_MODE and backend_rows_by_day:
        ensure_backend_days(daily, backend_rows_by_day)
    days = sorted(daily)
    if not days:
        return None
    return UsageChartData(daily=daily, days=days)


def add_backend_usage_traces(
    figure: go.Figure,
    usage: UsageChartData,
    backend_rows_by_day: DailyTokenValues,
) -> None:
    """Stack one band per backend, each in the hue its position picks."""
    backends = backend_names(backend_rows_by_day)
    for backend in backends:
        backend_color = color_for(
            backend,
            backends,
            explicit=BACKEND_COLORS,
        )
        add_token_stack_trace(
            figure,
            days=usage.days,
            token_series=[
                backend_rows_by_day.get(day, {}).get(backend, 0)
                for day in usage.days
            ],
            name=backend,
            color=backend_color,
        )


def add_token_type_usage_traces(
    figure: go.Figure,
    usage: UsageChartData,
) -> None:
    """Stack the input, output, and cache bands of every day.

    The pairs are listed in the order they stack in, so input is the band at
    the bottom of every day's column and cache the one on top.
    """
    for band, label in (
        (INPUT_BAND, "Input"),
        (OUTPUT_BAND, "Output"),
        (CACHE_BAND, "Cache"),
    ):
        add_token_stack_trace(
            figure,
            days=usage.days,
            token_series=[usage.daily[day][band] for day in usage.days],
            name=label,
            color=TOKEN_TYPE_COLORS[label],
        )


def add_usage_stack_traces(
    figure: go.Figure,
    usage: UsageChartData,
    backend_rows_by_day: DailyTokenValues | None,
    mode: str,
) -> None:
    """Stack the window in the mode the page asked for, where it can."""
    if mode == BACKEND_MODE and backend_rows_by_day:
        add_backend_usage_traces(figure, usage, backend_rows_by_day)
        return
    add_token_type_usage_traces(figure, usage)


def add_usage_cost_trace(
    figure: go.Figure,
    usage: UsageChartData,
) -> None:
    """Overlay the day's spend on the secondary axis, in dollars."""
    from plotly import graph_objects as go

    figure.add_trace(
        go.Scatter(
            x=date_axis(usage.days),
            y=[usage.daily[day][COST_BAND] for day in usage.days],
            name="Cost",
            mode="lines+markers",
            line={_COLOR_KEY: INK, "width": 2},
            marker={"size": 5, _COLOR_KEY: INK},
            yaxis="y2",
            hovertemplate="%{x}<br>Cost: $%{y:.2f}<extra></extra>",
        )
    )
