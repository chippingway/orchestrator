# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The seven reads a page's headline and lifecycle sections are drawn from.

Each one is a window already decided: the page hashed its filters into a cache
key, and what is left to say is which read that key is spent on. So the whole
of an adapter here is a query owner's read named beside the binding that issues
it, and everything under that -- the socket it runs on, the filters the key is
read back as, and the empty answer an unconfigured database yields -- is
decided by the owners it passes through rather than restated per section.

Each names the query owner that answers it rather than the `analytics.read`
facade forwarding the same objects, so these sections stay off a hop kept for
callers that predate those owners. Which owner that is follows what a read is
answered off: four are day-bucketed and the rollup family's, the review-round
split is what that bucket threw a column away for and the breakdown family's,
and the newest agent runs and the per-issue spend rows are scanned off the raw
events table under no bucket at all.

Three of the seven carry a decision a caller cannot re-derive. The recent
agent runs stop at the newest hundred, which is what keeps that list readable
on a long window -- and why the reliability tiles above it are reduced from the
window's own totals instead. The spend table is cut to the ranking depth the
KPI owner holds, read at call time so the rows fetched and the rows drawn
cannot become two different numbers. And the previous window is answered by the
KPI-only rollup rather than the full summary, because the delta pills and the
cost-trend banner want a handful of scalars: reusing the heavy shape would put
a second whole-window scan on every cold load.
"""
from __future__ import annotations

from orchestrator.observability.analytics.query import (
    breakdown_reads,
    issue_summaries,
    raw_reads,
    rollup_reads,
)
from orchestrator.observability.dashboard import filter_binding, kpis


DEFAULT_RECENT_AGENT_EXITS = 100


def read_summary(key: tuple):
    """Read the window totals every headline tile is reduced from."""
    return filter_binding.read_filtered(rollup_reads.get_summary, key)


def read_prev_kpi(key: tuple):
    """Read the previous window's scalar totals for the KPI comparisons."""
    return filter_binding.read_filtered(rollup_reads.get_kpi_prev, key)


def read_time_series(key: tuple):
    """Read the daily event, cost, and token cells a chart is plotted from."""
    return filter_binding.read_filtered(rollup_reads.get_time_series, key)


def read_stage_breakdown(key: tuple):
    """Read the per-stage activity and cost the window accumulated."""
    return filter_binding.read_filtered(rollup_reads.get_stage_breakdown, key)


def read_recent_agent_exits(key: tuple):
    """Read the newest agent runs, capped at what a run list can show."""
    return filter_binding.read_filtered(
        raw_reads.get_recent_agent_exits,
        key,
        limit=DEFAULT_RECENT_AGENT_EXITS,
    )


def read_top_cost_issues(key: tuple):
    """Read the window's issues cost-first, cut to the ranking depth."""
    return filter_binding.read_filtered(
        raw_reads.get_issues,
        key,
        limit=kpis.DEFAULT_EXPENSIVE_LIMIT,
        sort_by=issue_summaries.SORT_BY_COST,
    )


def read_review_round(key: tuple):
    """Read the development and review cost each round of the window cost."""
    return filter_binding.read_filtered(
        breakdown_reads.get_review_round_breakdown,
        key,
    )
