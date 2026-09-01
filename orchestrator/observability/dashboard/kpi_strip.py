# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The four tiles a window opens with, assembled from what it was read as.

This is where a page's first-wave rows become the strip above every panel: the
window's own aggregate and the one before it, the day series, the throughput
days, and the review-round split arrive together and leave as four display
entries plus the resolved / rejected pair the reliability tiles are also
reported with. Everything a tile shows is decided here rather than inside a
Streamlit run, so what an operator reads is testable without one.

The reductions themselves belong to `kpis`, and the lines under the tiles to
`kpi_series`; what this owner adds is which of them each tile reports and how
that reading is spelled. Two of those spellings carry a decision. Cost per
resolved issue is an em dash rather than a zero or a division when nothing was
resolved, because a window that resolved nothing has no such cost and printing
one would be a number an operator could act on. The rework share falls back to
zero the same way when no review round recorded any spend at all, so an
unpriced window reports no rework instead of failing to draw the tile.

The strip is handed the theme rather than importing it, because the module a
page renders through is the one whose formatters and hues a tile has to match
-- the page hands its own theme in, and the tiles cannot end up set in a
second one.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from orchestrator.observability.analytics.query.overview_models import Summary
from orchestrator.observability.dashboard.kpi_series import (
    DailyKpiSeries,
    daily_kpi_series,
    summary_total_tokens,
    throughput_totals,
)
from orchestrator.observability.dashboard.kpis import kpi_delta, rework_totals


# The keys the strip's HTML builder reads each entry back by.
_LABEL_KEY = "label"
_VALUE_KEY = "value"
_DELTA_KEY = "delta"
_SUBTITLE_KEY = "sub"
_SPARK_KEY = "spark"
KpiStripData = tuple[list[dict[str, Any]], int, int]


@dataclass(frozen=True)
class KpiInputs:
    """Everything one strip is built from, as the first wave handed it back."""

    theme: Any
    summary: Summary
    prev_summary: Summary
    ts_points: Sequence[Any]
    throughput_rows: Sequence[Any]
    review_round_rows: Sequence[Any]
    days_in_window: int


@dataclass(frozen=True)
class KpiTotals:
    """The window reduced to the eight scalars the four tiles are read off."""

    cost: float
    tokens: int
    previous_cost: float
    previous_tokens: int
    resolved: int
    rejected: int
    review_cost: float
    rework_cost: float


def kpi_totals(inputs: KpiInputs) -> KpiTotals:
    """Reduce a window and the one before it to the scalars a tile reports."""
    throughput = throughput_totals(inputs.throughput_rows)
    review_costs = rework_totals(inputs.review_round_rows)
    return KpiTotals(
        cost=float(inputs.summary.total_cost_usd or 0),
        tokens=summary_total_tokens(inputs.summary),
        previous_cost=float(inputs.prev_summary.total_cost_usd or 0),
        previous_tokens=summary_total_tokens(inputs.prev_summary),
        resolved=throughput[0],
        rejected=throughput[1],
        review_cost=review_costs[0],
        rework_cost=review_costs[1],
    )


def cost_per_resolved(totals: KpiTotals) -> str:
    """What one resolved issue cost, or an em dash when none were."""
    if totals.resolved <= 0:
        return "—"
    return "${}".format(format(totals.cost / totals.resolved, ",.2f"))


def kpi_strip_entries(
    inputs: KpiInputs,
    totals: KpiTotals,
    daily: DailyKpiSeries,
    rework_share: float,
) -> list[dict[str, Any]]:
    """The four entries the strip renders, in the order they are drawn."""
    daily_cost = inputs.theme.fmt_money(totals.cost / inputs.days_in_window)
    daily_tokens = inputs.theme.fmt_tokens(totals.tokens / inputs.days_in_window)
    rework_pct = rework_share * 100
    rework_cost = inputs.theme.fmt_money_exact(totals.rework_cost)
    return [
        {
            _LABEL_KEY: "Total spend",
            _VALUE_KEY: inputs.theme.fmt_money_exact(totals.cost),
            _DELTA_KEY: kpi_delta(totals.cost, totals.previous_cost),
            _SUBTITLE_KEY: f"{daily_cost}/day",
            _SPARK_KEY: daily.cost,
            "spark_color": inputs.theme.ACCENT,
        },
        {
            _LABEL_KEY: "Total tokens",
            _VALUE_KEY: inputs.theme.fmt_tokens(totals.tokens),
            _DELTA_KEY: kpi_delta(totals.tokens, totals.previous_tokens),
            _SUBTITLE_KEY: f"{daily_tokens}/day",
            _SPARK_KEY: daily.tokens,
            "spark_color": inputs.theme.TOKEN_TYPE_COLORS["Input"],
        },
        {
            _LABEL_KEY: "Cost / resolved issue",
            _VALUE_KEY: cost_per_resolved(totals),
            _DELTA_KEY: None,
            _SUBTITLE_KEY: (
                f"{totals.resolved} resolved · {totals.rejected} rejected"
            ),
            _SPARK_KEY: daily.done,
            "spark_color": inputs.theme.TOKEN_TYPE_COLORS["Cache"],
        },
        {
            _LABEL_KEY: "Rework share",
            _VALUE_KEY: f"{rework_pct:.0f}%",
            _DELTA_KEY: None,
            _SUBTITLE_KEY: f"{rework_cost} in review rounds >= 1",
            _SPARK_KEY: None,
        },
    ]


def build_kpi_strip_data(inputs: KpiInputs) -> KpiStripData:
    """Build KPI dictionaries and throughput totals."""
    totals = kpi_totals(inputs)
    rework_share = (
        totals.rework_cost / totals.review_cost
        if totals.review_cost > 0
        else float(0)
    )
    daily = daily_kpi_series(
        ts_points=inputs.ts_points,
        throughput_rows=inputs.throughput_rows,
    )
    kpis = kpi_strip_entries(inputs, totals, daily, rework_share)
    return kpis, totals.resolved, totals.rejected
