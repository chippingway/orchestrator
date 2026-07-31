# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical summary-query import site, answered by the query owner.

The three names are the owner's own functions, so the one round-trip a window's
totals and both its breakdowns come back from is built once whichever module a
caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.summary_queries import (
    build_summary_sql as _build_summary_sql,
    build_summary_where as _build_summary_where,
    query_summary_rows as _query_summary_rows,
)


_COMPATIBILITY_EXPORTS = (
    _build_summary_sql,
    _build_summary_where,
    _query_summary_rows,
)
