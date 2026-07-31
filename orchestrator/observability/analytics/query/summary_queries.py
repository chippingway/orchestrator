# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Asking one window for its totals and both its breakdowns at once.

A page frames a window with three answers -- what it totalled, how the events
split, how the stages split -- and this is the single query all three come back
from. The CTE applies the window predicate once and the three `UNION ALL`
branches read it back tagged by a `kind` discriminator, so a page pays one
round-trip instead of three scans of the same day range.

Two shapes in the SELECT list are load-bearing rather than incidental. GitHub
issue numbers are only unique within a repository, so the distinct-issue count
is over `(repo, issue)` pairs -- counting bare `issue` would collapse
`owner/a#1` and `owner/b#1` into one. And the agent-run counters narrow to
`event = 'agent_exit'`, so a non-exit bucket that happens to carry an exit code
never inflates them.

Neither branch is ordered in SQL. The ranking a page reads them in is applied
after the query, which leaves PostgreSQL free to pick an aggregate plan without
an ordering constraint on top of it.
"""

from __future__ import annotations

from typing import Any

from orchestrator.observability.analytics.query.execution import ReadQuery
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.predicates import (
    DAILY_ROLLUP_VIEW,
    build_rollup_window_where,
)


def build_summary_where(
    filters: WindowFilters,
) -> tuple[str, list[Any]]:
    """Build the predicate and bound values for one summary window."""
    return build_rollup_window_where(filters)


def build_summary_sql(where_clause: str) -> str:
    """Build the single rollup query for totals and breakdowns."""
    return (
        "WITH win AS ("
        "SELECT event, stage, repo, issue, "
        "event_count, failed_count, timed_out_count, "
        "total_cost_usd, total_input_tokens, total_output_tokens, "
        "total_cache_read_tokens, total_cache_write_tokens "
        f"FROM {DAILY_ROLLUP_VIEW}{where_clause}"
        ") "
        "SELECT 't' AS kind, NULL::text AS label, "
        "COALESCE(SUM(event_count), 0) AS count_val, "
        "COUNT(DISTINCT (repo, issue)) AS distinct_issues, "
        "COUNT(DISTINCT repo) AS distinct_repos, "
        "COALESCE(SUM(total_cost_usd), 0) AS total_cost_usd, "
        "COALESCE(SUM(total_input_tokens), 0) AS total_input_tokens, "
        "COALESCE(SUM(total_output_tokens), 0) AS total_output_tokens, "
        "COALESCE(SUM(CASE WHEN event = 'agent_exit' "
        "                  THEN event_count ELSE 0 END), 0) "
        "  AS total_agent_runs, "
        "COALESCE(SUM(CASE WHEN event = 'agent_exit' "
        "                  THEN failed_count ELSE 0 END), 0) "
        "  AS failed_agent_runs, "
        "COALESCE(SUM(total_cache_read_tokens), 0) "
        "  AS total_cache_read_tokens, "
        "COALESCE(SUM(total_cache_write_tokens), 0) "
        "  AS total_cache_write_tokens, "
        "COALESCE(SUM(timed_out_count), 0) AS timed_out_agent_runs "
        "FROM win "
        "UNION ALL "
        "SELECT 'e', event, COALESCE(SUM(event_count), 0), "
        "NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL "
        "FROM win GROUP BY event "
        "UNION ALL "
        "SELECT 's', stage, COALESCE(SUM(event_count), 0), "
        "NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL "
        "FROM win WHERE stage IS NOT NULL GROUP BY stage"
    )


def query_summary_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[tuple]:
    """Execute one summary query using the requested connection path."""
    where_clause, query_parameters = build_summary_where(filters)
    query_sql = build_summary_sql(where_clause)
    return query.select(query_sql, query_parameters)
