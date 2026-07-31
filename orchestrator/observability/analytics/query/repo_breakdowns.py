# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How much of one window's activity and spend each repository accounts for.

A bare `COUNT(DISTINCT issue)` is safe here only because the grouping is by
repository: issue numbers repeat across repositories, so the count is
per-repository already and cannot collapse two issues that merely share a
number. Agent runs are counted as the `event = 'agent_exit'` subset of the same
buckets, so the run column and the cost column beside it describe the same
rows. Ties on event volume break on the repository name, so redrawing the same
window returns the same order.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.cost_models import RepoBreakdownRow
from orchestrator.observability.analytics.query.execution import ReadQuery
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.predicates import (
    DAILY_ROLLUP_VIEW,
    build_rollup_window_where,
)
from orchestrator.observability.analytics.query.row_cells import cost_cell


def repo_breakdown_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[RepoBreakdownRow]:
    """Return one aggregate row per repository in the selected window."""
    where, bindings = build_rollup_window_where(filters)
    rows = query.select(
        "SELECT repo, "
        "COUNT(DISTINCT issue) AS repo_issues, "
        "COALESCE(SUM(event_count), 0) AS repo_events, "
        "COALESCE(SUM(CASE WHEN event = 'agent_exit' "
        "                  THEN event_count ELSE 0 END), 0) "
        "  AS repo_agent_exits, "
        "COALESCE(SUM(total_cost_usd), 0) AS repo_cost_usd "
        f"FROM {DAILY_ROLLUP_VIEW}{where} "
        "GROUP BY repo "
        "ORDER BY repo_events DESC, repo ASC",
        bindings,
    )
    return [
        RepoBreakdownRow(
            repo=row[0],
            issues=int(row[1] or 0),
            events=int(row[2] or 0),
            agent_exits=int(row[3] or 0),
            total_cost_usd=cost_cell(row, 4),
        )
        for row in rows
    ]
