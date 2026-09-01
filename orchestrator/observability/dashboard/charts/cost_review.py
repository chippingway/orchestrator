# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The per-review-round split of a window's spend, first pass on top.

One row per review round carrying two bars side by side: what development
spent reaching that round and what review spent judging it. Each bar is cut in
two -- what the model was billed at full price and what it was billed at the
cache rate -- and the halves stack within their own bar, so a bar's length is
still that role's whole spend for the round and the split inside it reads as
the share the cache paid for. Only the outer half carries the dollar text,
which is what labels a bar once instead of once per segment. The two roles are
offset into groups of their own so they share a row rather than stacking into
each other, and the legend is read back to front so its entries fall in the
order the bars are drawn in.

Rounds are ordered by the round itself rather than by spend, because a round
number is an ordinal and what the panel is read for is the shape of the rework
curve -- ranking the rows by cost would hide it. A bucket the window holds no
rows for drops out rather than drawing an empty row, and the runs that carried
no round at all come last under a label of their own: they are unattributed
rather than late. The sub-line counts the two roles' runs separately, because
the bars beside it are drawn from two different populations and one combined
count would explain neither.

Both halves of a role's bar are tinted from that role's one hue, the same
treatment the per-stage split gives its own halves and reached from there
rather than restated, so a cache segment here and one on the panel beside it
are the same shade. A row carries two bars rather than one, so the panel is
sized by a row height of its own rather than the shared default, and the whole
series is flipped on the way out, every column together, because a Plotly bar
axis draws the first row at the bottom and the initial pass belongs on top.

A window with nothing to draw is the shared placeholder at the height the
ranking owner pins an empty cost panel to, which is the one value taken from
there. It answers in two ways rather than one: no rows at all is a filter that
matched no agent exits, while rows carrying neither development nor review
runs is a window whose spend was all something else. An operator told "no
data" for the second would go looking for a broken query.

Plotly lives in the optional `dashboard` dependency group, so the figure is
built with an import inside the call: importing this owner has to work in the
default install, which does not carry it.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from orchestrator.observability.analytics.query.cost_models import (
    ReviewRoundBucketRow,
)
from orchestrator.observability.dashboard.charts.cost_horizontal import (
    DEFAULT_CHART_HEIGHT,
)
from orchestrator.observability.dashboard.charts.cost_layout import (
    CostBarTrace,
    HorizontalCostLayout,
    apply_horizontal_cost_layout,
    cost_bar_trace,
)
from orchestrator.observability.dashboard.charts.cost_stage import (
    CACHE_LIGHTEN,
    lighten_hex,
)
from orchestrator.observability.dashboard.charts.primitives import (
    empty_figure,
    horizontal_legend,
    reverse_lists,
    two_line_y_ticks,
)
from orchestrator.observability.dashboard.palette import AGENT_ROLE_COLORS

if TYPE_CHECKING:
    from plotly import graph_objects as go

# A row here carries two bars where a ranking row carries one, so it is given
# more of the panel than the shared default allows.
REVIEW_BAR_ROW_HEIGHT = 44
REVIEW_BAR_EXTRA_HEIGHT = 90

# How a bucket is read on the axis. The raw keys are what the read model
# buckets on; an operator reads the round rather than the key.
REVIEW_ROUND_LABELS = MappingProxyType({
    "0": "Initial",
    "1": "Round 1",
    "2": "Round 2",
    "3": "Round 3",
    "4": "Round 4",
    "5": "Round 5",
    "6+": "Rounds 6+",
    "unknown": "No review round",
})

# The order the rows are laid out in before the flip for the axis: by round,
# with the runs that carried none of them last.
REVIEW_ROUND_ORDER = ("0", "1", "2", "3", "4", "5", "6+", "unknown")


@dataclass(frozen=True)
class ReviewCostBars:
    """The eight columns of the split, each already in render order."""

    labels: Sequence[str]
    subs: Sequence[str]
    developer_no_cache: Sequence[float]
    developer_cache: Sequence[float]
    reviewer_no_cache: Sequence[float]
    reviewer_cache: Sequence[float]
    developer_totals: Sequence[float]
    reviewer_totals: Sequence[float]


def developer_cost_total(row: ReviewRoundBucketRow) -> float:
    """Add a round's two development halves back into one bar total."""
    return float(row.developer_no_cache_cost_usd or 0) + float(
        row.developer_cache_cost_usd or 0
    )


def reviewer_cost_total(row: ReviewRoundBucketRow) -> float:
    """Add a round's two review halves back into one bar total."""
    return float(row.reviewer_no_cache_cost_usd or 0) + float(
        row.reviewer_cache_cost_usd or 0
    )


def reverse_review_cost_bars(bars: ReviewCostBars) -> ReviewCostBars:
    """Flip the split so its initial pass is drawn at the top."""
    reversed_values = reverse_lists(
        bars.labels,
        bars.subs,
        bars.developer_no_cache,
        bars.developer_cache,
        bars.reviewer_no_cache,
        bars.reviewer_cache,
        bars.developer_totals,
        bars.reviewer_totals,
    )
    return ReviewCostBars(*reversed_values)


def review_cost_bars(
    rows: Sequence[ReviewRoundBucketRow],
) -> ReviewCostBars | None:
    """Order the rounds, label them, and flip them, or answer nothing."""
    by_bucket = {row.bucket: row for row in rows}
    ordered = [
        by_bucket[bucket]
        for bucket in REVIEW_ROUND_ORDER
        if bucket in by_bucket
    ]
    if not ordered:
        return None
    return reverse_review_cost_bars(
        ReviewCostBars(
            labels=[REVIEW_ROUND_LABELS.get(row.bucket, row.bucket) for row in ordered],
            subs=[
                f"{int(row.developer_runs or 0):,} dev / "
                f"{int(row.reviewer_runs or 0):,} review runs"
                for row in ordered
            ],
            developer_no_cache=[
                float(row.developer_no_cache_cost_usd or 0) for row in ordered
            ],
            developer_cache=[
                float(row.developer_cache_cost_usd or 0) for row in ordered
            ],
            reviewer_no_cache=[
                float(row.reviewer_no_cache_cost_usd or 0) for row in ordered
            ],
            reviewer_cache=[
                float(row.reviewer_cache_cost_usd or 0) for row in ordered
            ],
            developer_totals=[developer_cost_total(row) for row in ordered],
            reviewer_totals=[reviewer_cost_total(row) for row in ordered],
        )
    )


def review_cost_traces(
    bars: ReviewCostBars,
    y_ticks: Sequence[str],
) -> tuple[CostBarTrace, ...]:
    """Describe the four series, review first so development reads above it."""
    developer_color = AGENT_ROLE_COLORS["developer"]
    reviewer_color = AGENT_ROLE_COLORS["reviewer"]
    developer_cache_color = lighten_hex(developer_color, CACHE_LIGHTEN)
    reviewer_cache_color = lighten_hex(reviewer_color, CACHE_LIGHTEN)
    return (
        CostBarTrace(
            name="Review (no cache)",
            amounts=bars.reviewer_no_cache,
            y_ticks=y_ticks,
            color=reviewer_color,
            offsetgroup="reviewer",
            hover_label="Review (no cache)",
        ),
        CostBarTrace(
            name="Review (cache)",
            amounts=bars.reviewer_cache,
            y_ticks=y_ticks,
            color=reviewer_cache_color,
            offsetgroup="reviewer",
            totals=bars.reviewer_totals,
            hover_label="Review (cache)",
        ),
        CostBarTrace(
            name="Development (no cache)",
            amounts=bars.developer_no_cache,
            y_ticks=y_ticks,
            color=developer_color,
            offsetgroup="developer",
            hover_label="Development (no cache)",
        ),
        CostBarTrace(
            name="Development (cache)",
            amounts=bars.developer_cache,
            y_ticks=y_ticks,
            color=developer_cache_color,
            offsetgroup="developer",
            totals=bars.developer_totals,
            hover_label="Development (cache)",
        ),
    )


def cost_by_review_round(
    rows: Sequence[ReviewRoundBucketRow],
    *,
    height: int | None = None,
) -> go.Figure:
    """Build grouped cache and no-cache cost bars by review round."""
    from plotly import graph_objects as go

    if not rows:
        return empty_figure(
            "No `agent_exit` rows match the current filters.",
            height=height or DEFAULT_CHART_HEIGHT,
        )
    bars = review_cost_bars(rows)
    if bars is None:
        return empty_figure(
            "No development or review runs match the current filters.",
            height=height or DEFAULT_CHART_HEIGHT,
        )
    y_ticks = two_line_y_ticks(bars.labels, bars.subs)
    figure = go.Figure()
    for trace in review_cost_traces(bars, y_ticks):
        figure.add_trace(cost_bar_trace(trace))
    apply_horizontal_cost_layout(
        figure,
        HorizontalCostLayout(
            row_count=len(y_ticks),
            height=height,
            barmode="relative",
            legend=horizontal_legend(traceorder="reversed"),
            row_height=REVIEW_BAR_ROW_HEIGHT,
            extra_height=REVIEW_BAR_EXTRA_HEIGHT,
        ),
    )
    return figure
