# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical issue-summary import site, answered by the query owner.

The two sort modes and the set they belong to are the owner's own objects, so a
caller that validates `sort_by` here accepts exactly what the read accepts, and
the scan and projection beside them are the ones it runs.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.issue_summaries import (
    ISSUE_SORT_BY_OPTIONS as ISSUE_SORT_BY_OPTIONS,
    SORT_BY_COST as SORT_BY_COST,
    SORT_BY_LAST_SEEN as SORT_BY_LAST_SEEN,
    issue_order_sql as _issue_order_sql,
    issue_summary_from_row as _issue_summary_from_row,
    issue_summary_rows as _issue_summary_rows,
    issues_sql as _issues_sql,
)


_COMPATIBILITY_EXPORTS = (
    ISSUE_SORT_BY_OPTIONS,
    SORT_BY_COST,
    SORT_BY_LAST_SEEN,
    _issue_order_sql,
    _issue_summary_from_row,
    _issue_summary_rows,
    _issues_sql,
)
