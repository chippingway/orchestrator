# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One issue's event trace, oldest first.

The `(repo, issue)` pair the drill-down is keyed by is this read's own
condition, so it is spliced ahead of the generated predicate and its two
operands bind before the window's. Ordering ties break on `id`, which is the
insertion order, so two events recorded in the same instant still read back in
the order they happened.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from orchestrator.observability.analytics.query.conditions import prepend_where_condition
from orchestrator.observability.analytics.query.execution import ReadQuery
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.predicates import build_window_where
from orchestrator.observability.analytics.query.raw_values import float_or_none, int_or_none
from orchestrator.observability.analytics.query.run_models import IssueEventRow


def issue_event_from_row(row: Sequence[Any]) -> IssueEventRow:
    """Project one traced-event row onto its result model."""
    return IssueEventRow(
        ts=row[0],
        event=row[1],
        stage=row[2],
        duration_s=float_or_none(row[3]),
        event_result=row[4],
        agent_role=row[5],
        backend=row[6],
        exit_code=int_or_none(row[7]),
        cost_usd=float_or_none(row[8]),
    )


def issue_event_rows(
    query: ReadQuery,
    filters: WindowFilters,
    repo: str,
    issue: int,
) -> list[IssueEventRow]:
    """Return every selected event for one issue, oldest first."""
    where, bindings = build_window_where(filters)
    where = prepend_where_condition(where, "repo = %s AND issue = %s")
    rows = query.select(
        "SELECT ts, event, stage, duration_s, result, "
        "agent_role, backend, exit_code, cost_usd "
        f"FROM analytics_events{where} "
        "ORDER BY ts ASC, id ASC",
        [repo, int(issue), *bindings],
    )
    return [issue_event_from_row(row) for row in rows]
