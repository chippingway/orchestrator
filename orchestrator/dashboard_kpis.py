# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""KPI calculations for the analytics dashboard.

The pure numeric core behind the redesigned page: the KPI delta math
(`kpi_delta`), the reliability-tile triples (`reliability_tile_data`),
the top-cost issue ordering (`top_expensive_issues`), and the rework-
share aggregation (`rework_totals`). These take read-model rows /
`Summary` aggregates and return plain numbers, strings, and small
dataclasses so they stay testable without a live Streamlit run and
free of any rendering or Streamlit dependency.

The banners a page opens above those numbers are the insight owner's
under `observability/dashboard/`. The names they were historically
reached here under stay bound to that owner's own objects, so a caller
spelling one on this module and one spelling it on the owner cannot be
answered by two thresholds.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from orchestrator.analytics.read import IssueSummaryRow, Summary
from orchestrator.observability.dashboard import insights

DEFAULT_EXPENSIVE_LIMIT = 8

FAILURE_RATE_BANNER_THRESHOLD = insights.FAILURE_RATE_BANNER_THRESHOLD
UNPRICED_COVERAGE_THRESHOLD = insights.UNPRICED_COVERAGE_THRESHOLD
UNPRICED_COST_SOURCES = insights.UNPRICED_COST_SOURCES
InsightBanner = insights.InsightBanner
compute_insights = insights.compute_insights

# Bucket strings the review-round breakdown emits whose runs are
# "rework" (i.e. happened after the initial pass). Used to compute the
# rework share KPI. `get_review_round_breakdown` keeps rounds 3, 4 and
# 5 separate (only 6+ is grouped), so every post-initial round is
# listed explicitly here.
REWORK_BUCKETS: frozenset[str] = frozenset(
    ("1", "2", "3", "4", "5", "6+")
)


def kpi_delta(
    current: float, previous: float
) -> Optional[float]:
    """Relative change vs the previous window.

    Returns `(current - previous) / previous` (e.g. `0.25` = +25%) or
    `None` when `previous` is zero / negative so the dashboard hides
    the delta indicator rather than rendering an infinity. Negative
    `previous` values are not expected in this column set (counts,
    spend, tokens are all non-negative) but the guard keeps the
    helper safe to call from anywhere.
    """
    if previous <= 0:
        return None
    return (current - previous) / previous


def reliability_tile_data(
    summary: Summary,
    *,
    resolved: int = 0,
    rejected: int = 0,
) -> list[tuple[int, str, str]]:
    """`(value, label, tone)` triples for the six reliability tiles.

    Extracted from `main()` so the wiring stays testable without a
    live Streamlit run: every tile sources its number from a
    full-window aggregate on `Summary` (`total_agent_runs`,
    `failed_agent_runs`, `timed_out_agent_runs`) so a long window
    with more than `DEFAULT_RECENT_AGENT_EXITS` rows never silently
    undercounts the tile -- earlier drafts read timeouts off
    `get_recent_agent_exits` and missed any timeout outside the
    latest 100 rows.

    `resolved` / `rejected` are the per-day rollups summed by the
    caller from `get_throughput_breakdown`; they default to zero so
    callers that only care about the agent-run tiles can ignore the
    throughput axis.

    Tones (`"good"` / `"warn"` / `"bad"` / `""`) drive the CSS class
    applied to the tile; the caller never has to recompute them.
    """
    total_runs = int(summary.total_agent_runs or 0)
    failed = int(summary.failed_agent_runs or 0)
    timed_out = int(summary.timed_out_agent_runs or 0)
    success_pct = (
        (1.0 - failed / total_runs) * 100
        if total_runs > 0 else float()
    )
    return [
        (total_runs, "Agent runs", ""),
        (f"{success_pct:.0f}%", "Success rate", "good"),
        (int(resolved), "Resolved", "good"),
        (int(rejected), "Rejected", "warn" if rejected else ""),
        (failed, "Failures", "warn" if failed else ""),
        (timed_out, "Timeouts", "bad" if timed_out else ""),
    ]


def top_expensive_issues(
    rows: Sequence[IssueSummaryRow],
    *,
    limit: int = DEFAULT_EXPENSIVE_LIMIT,
) -> list[IssueSummaryRow]:
    """Issues sorted by total cost desc for the "where did spend go" table."""
    if limit <= 0:
        return []
    return sorted(rows, key=_expensive_issue_key)[:limit]


def _expensive_issue_key(row: IssueSummaryRow) -> tuple:
    cost = row.total_cost_usd
    if cost is None:
        cost = -1.0
    event_count = -int(row.event_count)
    issue_number = int(row.issue)
    return (-cost, event_count, row.repo, issue_number)


def rework_totals(
    rows: Sequence[Any],
) -> tuple[float, float]:
    """Return `(total_cost, rework_cost)` across review-round buckets.

    `rework_cost` sums the cost of every row whose `bucket` is in
    `REWORK_BUCKETS` (i.e. review round >= 1). `total_cost` sums
    every row, including the initial pass. Cost defaults to `0.0`
    when the row predates the `total_cost_usd` column.
    """
    total = sum(
        float(getattr(row, "total_cost_usd", 0) or 0) for row in rows
    )
    rework = sum(
        float(getattr(row, "total_cost_usd", 0) or 0)
        for row in rows
        if row.bucket in REWORK_BUCKETS
    )
    return total, rework
