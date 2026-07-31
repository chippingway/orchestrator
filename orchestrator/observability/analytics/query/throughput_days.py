# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How many issues each day resolved, and how many it turned away.

An issue reaches its end by entering one of two stages -- `done` for merged or
closed successfully, `rejected` for closed without a merge -- so this read is
about `stage_enter` rows and nothing else. The event is pinned rather than
filtered, and the caller's own event selection only decides whether the read
runs at all: a selection that leaves `stage_enter` out has nothing here to
count, so the read answers with no days rather than an empty scan.

The stage selection narrows instead of replacing. A caller that named
non-terminal stages is asking about work in flight, so intersecting its
selection with the two terminals leaves nothing and the read short-circuits;
naming one terminal narrows the scan to that one. Days come back ascending
because a throughput chart is read left to right.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional, Sequence

from orchestrator.observability.analytics.query.activity_models import ThroughputDayRow
from orchestrator.observability.analytics.query.conditions import prepend_where_condition
from orchestrator.observability.analytics.query.execution import ReadQuery
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.predicates import (
    DAILY_ROLLUP_VIEW,
    build_rollup_window_where,
)
from orchestrator.observability.analytics.query.row_cells import day_value

THROUGHPUT_RESOLVED_STAGES: tuple[str, ...] = ("done", "rejected")


def selected_throughput_stages(
    stages: Optional[Sequence[str]],
) -> tuple[str, ...]:
    """Narrow a caller's stage selection to the terminals this read counts."""
    if stages is None:
        return THROUGHPUT_RESOLVED_STAGES
    return tuple(stage for stage in stages if stage in THROUGHPUT_RESOLVED_STAGES)


def throughput_from_row(row: Sequence[Any]) -> ThroughputDayRow:
    """Project one day's terminal counts onto its result model."""
    return ThroughputDayRow(
        day=day_value(row[0]),
        resolved=int(row[1] or 0),
        rejected=int(row[2] or 0),
    )


def throughput_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[ThroughputDayRow]:
    """Return one resolved / rejected pair per day in the selected window."""
    if filters.events is not None and "stage_enter" not in filters.events:
        return []
    active_stages = selected_throughput_stages(filters.stages)
    if not active_stages:
        return []
    scoped_filters = replace(filters, events=None, stages=active_stages)
    where, bindings = build_rollup_window_where(scoped_filters)
    where = prepend_where_condition(where, "event = %s")
    bindings.insert(0, "stage_enter")
    rows = query.select(
        "SELECT day, "
        "COALESCE(SUM(CASE WHEN stage = 'done' "
        "                  THEN event_count ELSE 0 END), 0) AS resolved, "
        "COALESCE(SUM(CASE WHEN stage = 'rejected' "
        "                  THEN event_count ELSE 0 END), 0) AS rejected "
        f"FROM {DAILY_ROLLUP_VIEW}{where} "
        "GROUP BY day "
        "ORDER BY day ASC",
        bindings,
    )
    return [throughput_from_row(row) for row in rows]
