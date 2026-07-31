# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Raw event-breakdown query projection."""

from __future__ import annotations

from orchestrator.observability.analytics.query.execution import ReadQuery
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.predicates import build_window_where
from orchestrator.observability.analytics.query.run_models import EventBreakdown


def _event_breakdown_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[EventBreakdown]:
    where, bindings = build_window_where(filters)
    rows = query.select(
        f"SELECT event, COUNT(*) AS c FROM analytics_events{where} GROUP BY event ORDER BY c DESC, event ASC",
        bindings,
    )
    return [EventBreakdown(event=event, count=int(count)) for event, count in rows]
