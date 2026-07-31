# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How many of each event fired inside the selected window.

Counted off `analytics_events` itself, so the breakdown stays exact against
whatever timestamp bounds the window carries rather than the day the
day-bucketed rollup would round them to. Ties break on the event name, so
redrawing the same window cannot reshuffle the table.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.execution import ReadQuery
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.predicates import build_window_where
from orchestrator.observability.analytics.query.run_models import EventBreakdown


def event_breakdown_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[EventBreakdown]:
    """Return one count per event inside the filtered window."""
    where, bindings = build_window_where(filters)
    rows = query.select(
        f"SELECT event, COUNT(*) AS c FROM analytics_events{where} GROUP BY event ORDER BY c DESC, event ASC",
        bindings,
    )
    return [EventBreakdown(event=event, count=int(count)) for event, count in rows]
