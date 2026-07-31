# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""KPI and daily-series rollup query projections."""

from __future__ import annotations

from typing import Any, Sequence

from orchestrator.analytics._read_row_values import (
    _cost_cell,
    _day_value,
    _row_value,
)
from orchestrator.observability.analytics.query.execution import ReadQuery
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.overview_models import (
    Summary,
    TimeSeriesPoint,
)
from orchestrator.observability.analytics.query.predicates import (
    DAILY_ROLLUP_VIEW,
    build_rollup_window_where,
)


def _kpi_prev_sql(where: str) -> str:
    return (
        "SELECT "
        "COALESCE(SUM(total_cost_usd), 0) AS total_cost_usd, "
        "COALESCE(SUM(total_input_tokens), 0) AS total_input_tokens, "
        "COALESCE(SUM(total_output_tokens), 0) AS total_output_tokens, "
        "COALESCE(SUM(total_cache_read_tokens), 0) "
        "  AS total_cache_read_tokens, "
        "COALESCE(SUM(total_cache_write_tokens), 0) "
        "  AS total_cache_write_tokens, "
        "COALESCE(SUM(CASE WHEN event = 'agent_exit' "
        "                  THEN event_count ELSE 0 END), 0) "
        "  AS total_agent_runs "
        f"FROM {DAILY_ROLLUP_VIEW}{where}"
    )


def _kpi_prev_summary(
    query: ReadQuery,
    filters: WindowFilters,
) -> Summary:
    where, bindings = build_rollup_window_where(filters)
    rows = query.select(_kpi_prev_sql(where), bindings)
    if not rows:
        return Summary()
    row = rows[0]
    return Summary(
        total_cost_usd=_cost_cell(row, 0),
        total_input_tokens=int(row[1] or 0),
        total_output_tokens=int(row[2] or 0),
        total_cache_read_tokens=int(row[3] or 0),
        total_cache_write_tokens=int(row[4] or 0),
        total_agent_runs=int(_row_value(row, 5) or 0),
    )


def _time_series_from_row(row: Sequence[Any]) -> TimeSeriesPoint:
    return TimeSeriesPoint(
        day=_day_value(row[0]),
        event=row[1],
        count=int(row[2]),
        cost_usd=_cost_cell(row, 3),
        input_tokens=int(_row_value(row, 4) or 0),
        output_tokens=int(_row_value(row, 5) or 0),
        cache_read_tokens=int(_row_value(row, 6) or 0),
        cache_write_tokens=int(_row_value(row, 7) or 0),
    )


def _time_series_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[TimeSeriesPoint]:
    where, bindings = build_rollup_window_where(filters)
    rows = query.select(
        "SELECT day, event, "
        "COALESCE(SUM(event_count), 0) AS c, "
        "COALESCE(SUM(total_cost_usd), 0) AS day_cost_usd, "
        "COALESCE(SUM(total_input_tokens), 0) AS day_input_tokens, "
        "COALESCE(SUM(total_output_tokens), 0) AS day_output_tokens, "
        "COALESCE(SUM(total_cache_read_tokens), 0) "
        "  AS day_cache_read_tokens, "
        "COALESCE(SUM(total_cache_write_tokens), 0) "
        "  AS day_cache_write_tokens "
        f"FROM {DAILY_ROLLUP_VIEW}{where} "
        "GROUP BY day, event "
        "ORDER BY day ASC, event ASC",
        bindings,
    )
    return [_time_series_from_row(row) for row in rows]
