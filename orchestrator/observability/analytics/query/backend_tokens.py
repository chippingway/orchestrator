# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What each backend spent in tokens, day by day across the window.

The series is aggregated off the agent-run view rather than assembled from the
newest-runs read a table elsewhere on the page is drawn from, so every run in
the window is counted instead of the capped subset that read returns -- a
backend busy early in a long window would otherwise flatten toward zero as the
cap trimmed its runs away. That keeps the per-day stack in lockstep with the
cost line and the window totals beside it.

Each band a chart stacks is one `(day, backend)` cell, and a run that recorded
no backend buckets under `unknown` rather than dropping out of the day's total.
"""

from __future__ import annotations

from typing import Any, Sequence

from orchestrator.observability.analytics.query.activity_models import (
    BackendDailyTokensRow,
)
from orchestrator.observability.analytics.query.execution import ReadQuery
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.predicates import build_view_window_where
from orchestrator.observability.analytics.query.row_cells import day_value


def backend_daily_tokens_from_row(
    row: Sequence[Any],
) -> BackendDailyTokensRow:
    """Project one per-day-and-backend token row onto its result model."""
    return BackendDailyTokensRow(
        day=day_value(row[0]),
        backend=str(row[1]),
        total_tokens=int(row[2] or 0),
    )


def backend_daily_token_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[BackendDailyTokensRow]:
    """Return one token total per `(day, backend)` cell in the window."""
    daily_where, daily_bindings = build_view_window_where(filters)
    rows = query.select(
        "SELECT "
        "date_trunc('day', ts)::date AS day, "
        "COALESCE(backend, 'unknown') AS backend_label, "
        "COALESCE(SUM("
        "  COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0) + "
        "  COALESCE(cache_read_tokens, 0) + "
        "  COALESCE(cache_write_tokens, 0)"
        "), 0) AS day_backend_tokens "
        f"FROM analytics_agent_runs{daily_where} "
        "GROUP BY day, backend_label "
        "ORDER BY day ASC, backend_label ASC",
        daily_bindings,
    )
    return [backend_daily_tokens_from_row(row) for row in rows]
