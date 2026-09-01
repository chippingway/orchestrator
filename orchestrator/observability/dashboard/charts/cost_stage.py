# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The per-stage split of a window's spend, dearest stage on top.

One bar per workflow stage, cut in two: what the model was billed at full
price, and what it was billed at the cache rate. The two halves are stacked
rather than drawn side by side, so a bar's length is still the stage's whole
spend and the split inside it reads as the share the cache paid for. Only the
outer half carries the dollar text, which is what labels a bar once instead of
once per segment.

The two halves are tinted from one hue -- the stage's own color, and a
translucent shade of it for the cache half -- because a separate palette for
the cache segments would read as eight stages rather than four stages split two
ways. That shading is the color treatment the per-review-round split reaches
for as well, which is why the lightening lives here rather than inside the
stacking.

A row that carries neither half but does carry a total is a window read before
the split existed, and plotting it straight would draw an empty bar for spend
that happened. The whole total becomes the no-cache half instead, so the bar
still reads at its true length. The sub-line counts `runs` -- the agent exits
`StageBreakdown.count` is a superset of -- because the spend a bar is drawn
from is what those exits reported.

Stages are ranked by spend and the whole series is flipped on the way out,
every column together, because a Plotly bar axis draws the first row at the
bottom and the dearest stage belongs on top.

A window with no stages is the shared placeholder at the height the ranking
owner beside this one pins an empty cost panel to, which is the one value taken
from there: a split with nothing to draw and a ranking with nothing to rank sit
in the same card on the same row of the page.

Plotly lives in the optional `dashboard` dependency group, so the figure is
built with an import inside the call: importing this owner has to work in the
default install, which does not carry it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from orchestrator.observability.analytics.query.run_models import StageBreakdown
from orchestrator.observability.dashboard.charts.cost_horizontal import (
    DEFAULT_CHART_HEIGHT,
)
from orchestrator.observability.dashboard.charts.cost_layout import (
    CostBarTrace,
    HorizontalCostLayout,
    apply_horizontal_cost_layout,
    cost_bar_trace,
)
from orchestrator.observability.dashboard.charts.primitives import (
    empty_figure,
    horizontal_legend,
    reverse_lists,
    two_line_y_ticks,
)
from orchestrator.observability.dashboard.palette import STAGE_COLORS, color_for

if TYPE_CHECKING:
    from plotly import graph_objects as go

# How far towards transparent a stage's hue is taken for its cache half. Far
# enough that the two halves of a bar are told apart at a glance, near enough
# that they still read as one stage.
CACHE_LIGHTEN = 0.45

HEX_BASE = 16


@dataclass(frozen=True)
class StageCostBars:
    """The seven columns of the split, each already in render order."""

    labels: Sequence[str]
    subs: Sequence[str]
    no_cache: Sequence[float]
    cache: Sequence[float]
    totals: Sequence[float]
    colors: Sequence[str]
    cache_colors: Sequence[str]


def stage_no_cache_cost(row: StageBreakdown) -> float:
    """Read the full-price half, falling back to the whole total."""
    no_cache = float(row.no_cache_cost_usd or 0)
    cache = float(row.cache_cost_usd or 0)
    total = float(row.total_cost_usd or 0)
    if no_cache == 0 and cache == 0 and total > 0:
        return total
    return no_cache


def reverse_stage_cost_bars(bars: StageCostBars) -> StageCostBars:
    """Flip the split so its dearest stage is drawn at the top."""
    reversed_values = reverse_lists(
        bars.labels,
        bars.subs,
        bars.no_cache,
        bars.cache,
        bars.totals,
        bars.colors,
        bars.cache_colors,
    )
    return StageCostBars(*reversed_values)


def stage_cost_bars(rows: Sequence[StageBreakdown]) -> StageCostBars:
    """Rank the stages, tint both halves of each, and flip them."""
    ordered = sorted(rows, key=stage_cost_sort_key)
    colors = [
        color_for(row.stage, explicit=STAGE_COLORS)
        for row in ordered
    ]
    return reverse_stage_cost_bars(
        StageCostBars(
            labels=[row.stage for row in ordered],
            subs=[f"{int(row.runs or 0):,} runs" for row in ordered],
            no_cache=[stage_no_cache_cost(row) for row in ordered],
            cache=[float(row.cache_cost_usd or 0) for row in ordered],
            totals=[float(row.total_cost_usd or 0) for row in ordered],
            colors=colors,
            cache_colors=[lighten_hex(color, CACHE_LIGHTEN) for color in colors],
        )
    )


def stage_cost_sort_key(row: StageBreakdown) -> float:
    """Rank a stage by spend descending, counting an unpriced one as zero."""
    return -float(row.total_cost_usd or 0)


def cost_by_stage(
    rows: Sequence[StageBreakdown],
    *,
    height: int | None = None,
) -> go.Figure:
    """Build stacked cache and no-cache cost bars per workflow stage."""
    from plotly import graph_objects as go

    if not rows:
        return empty_figure(
            "No stage data matches the current filters.",
            height=height or DEFAULT_CHART_HEIGHT,
        )
    bars = stage_cost_bars(rows)
    y_ticks = two_line_y_ticks(bars.labels, bars.subs)
    figure = go.Figure()
    figure.add_trace(
        cost_bar_trace(
            CostBarTrace(
                name="No cache",
                amounts=bars.no_cache,
                y_ticks=y_ticks,
                color=bars.colors,
                hover_label="No cache",
            )
        )
    )
    figure.add_trace(
        cost_bar_trace(
            CostBarTrace(
                name="Cache",
                amounts=bars.cache,
                y_ticks=y_ticks,
                color=bars.cache_colors,
                hover_label="Cache",
                totals=bars.totals,
            )
        )
    )
    apply_horizontal_cost_layout(
        figure,
        HorizontalCostLayout(
            row_count=len(y_ticks),
            height=height,
            barmode="stack",
            legend=horizontal_legend(),
        ),
    )
    return figure


def lighten_hex(hex_color: str, alpha: float) -> str:
    """Restate a hex color as the same hue at the given opacity."""
    hex_digits = hex_color.lstrip("#")
    red = int(hex_digits[:2], HEX_BASE)
    green = int(hex_digits[2:4], HEX_BASE)
    blue = int(hex_digits[4:6], HEX_BASE)
    return f"rgba({red},{green},{blue},{alpha:.2f})"
