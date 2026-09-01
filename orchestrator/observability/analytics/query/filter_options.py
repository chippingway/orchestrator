# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The distinct values a window's filters offer, in one scan per column.

Five dropdowns would be five `SELECT DISTINCT` round-trips; the union asks for
all of them at once, tagging each value with the column it came from so one
result set still buckets cleanly. Each leg keeps its own `IS NOT NULL` so the
partial-scan plan per column survives the union.

The bucketing is done here rather than in SQL because the dropdown order is a
presentation choice: values sort ascending in Python, and a tag the reader does
not know is dropped rather than routed to a bucket the result model has no
field for.
"""

from __future__ import annotations

from collections.abc import Sequence

from orchestrator.observability.analytics.query.overview_models import FilterOptions

FILTER_OPTION_COLUMNS: tuple[str, ...] = (
    "repo",
    "event",
    "stage",
    "backend",
    "agent_role",
)


def filter_options_sql() -> str:
    """Build the unioned distinct-value scan across the five columns."""
    return " UNION ".join(
        f"SELECT '{column}' AS dim, {column} AS value FROM analytics_events WHERE {column} IS NOT NULL"
        for column in FILTER_OPTION_COLUMNS
    )


def filter_options_from_rows(rows: Sequence[tuple]) -> FilterOptions:
    """Bucket the tagged union rows into one sorted list per dropdown."""
    buckets: dict[str, list[str]] = {column: [] for column in FILTER_OPTION_COLUMNS}
    for row in rows:
        if not row or row[1] is None:
            continue
        dimension = row[0]
        bucket = buckets.get(dimension)
        if bucket is not None:
            bucket.append(row[1])
    for option_names in buckets.values():
        option_names.sort()
    return FilterOptions(
        repos=tuple(buckets["repo"]),
        events=tuple(buckets["event"]),
        stages=tuple(buckets["stage"]),
        backends=tuple(buckets["backend"]),
        agent_roles=tuple(buckets["agent_role"]),
    )
