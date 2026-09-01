# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The panel every horizontal cost family is laid out in, and a bar in it.

Three families draw dollars along a horizontal axis -- the generic ranking, the
per-stage split, and the per-review-round split -- and they read as one page
only while they share a frame. This owner is that frame: the same left gutter
wide enough for a two-line label, the same `USD` axis under a `$` tick prefix,
and one row height per bar over the fixed base unless the caller pinned a
height. A family assembling its own layout would part company with the ones
beside it the first time a margin or a row height moved.

A bar arrives as a frozen request rather than a pile of keyword arguments,
because what differs between the families is which halves are present: a
side-by-side split names an offsetgroup so its bars share a y bucket, and only
the outer trace of a stack carries the total, so the amount is labelled once per
bar instead of once per segment.

Plotly lives in the optional `dashboard` dependency group, so the helper that
builds a trace imports it at call time: importing this owner has to work in the
default install, which does not carry it.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Sequence

from orchestrator.observability.dashboard.charts.primitives import (
    HORIZONTAL_BAR_EXTRA_HEIGHT,
    HORIZONTAL_BAR_ROW_HEIGHT,
    horizontal_panel_height,
    money_text,
    monospace_textfont,
)
from orchestrator.observability.dashboard.layout import base_layout

if TYPE_CHECKING:
    from plotly import graph_objects as go

# The gutter a two-line label is drawn in, plus the room the outside value
# label needs past the longest bar. The top margin stays whatever the shared
# layout set, so a titled panel keeps its heading clear.
HORIZONTAL_BAR_MARGIN = MappingProxyType({"l": 160, "r": 64, "b": 32})


@dataclass(frozen=True)
class HorizontalCostLayout:
    """What one horizontal cost panel is framed and sized by."""

    row_count: int
    height: int | None = None
    title: str | None = None
    barmode: str | None = None
    legend: dict[str, object] | None = None
    row_height: int = HORIZONTAL_BAR_ROW_HEIGHT
    extra_height: int = HORIZONTAL_BAR_EXTRA_HEIGHT


def apply_horizontal_cost_layout(
    figure: go.Figure,
    options: HorizontalCostLayout,
) -> None:
    """Frame a built figure as one of the horizontal cost panels."""
    layout = base_layout(title=options.title)
    if options.barmode is not None:
        layout["barmode"] = options.barmode
    if options.legend is not None:
        layout["legend"] = options.legend
    layout["margin"] = {
        **HORIZONTAL_BAR_MARGIN,
        "t": layout["margin"]["t"],
    }
    layout["height"] = horizontal_panel_height(
        options.row_count,
        height=options.height,
        row_height=options.row_height,
        extra_height=options.extra_height,
    )
    figure.update_layout(**layout)
    figure.update_xaxes(
        title_text="USD",
        tickprefix="$",
        showline=False,
        zeroline=False,
    )
    figure.update_yaxes(automargin=True, showline=False, ticks="")


@dataclass(frozen=True)
class CostBarTrace:
    """One series of bars: what it is called, costs, and is tinted by."""

    name: str
    amounts: Sequence[float]
    y_ticks: Sequence[str]
    color: object
    hover_label: str
    offsetgroup: str | None = None
    totals: Sequence[float] | None = None


def cost_bar_trace(options: CostBarTrace) -> go.Bar:
    """Build the requested series as a horizontal bar trace."""
    from plotly import graph_objects as go

    trace_kwargs = {
        "x": list(options.amounts),
        "y": list(options.y_ticks),
        "name": options.name,
        "orientation": "h",
        "marker_color": options.color,
        "cliponaxis": False,
        "hovertemplate": (
            f"%{{y}}<br>{options.hover_label}: $%{{x:,.2f}}<extra></extra>"
        ),
    }
    if options.offsetgroup is not None:
        trace_kwargs["offsetgroup"] = options.offsetgroup
    if options.totals is not None:
        trace_kwargs["text"] = money_text(options.totals)
        trace_kwargs["textposition"] = "outside"
        trace_kwargs["textfont"] = monospace_textfont()
    return go.Bar(**trace_kwargs)
