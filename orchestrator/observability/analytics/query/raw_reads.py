# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The six reads answered off the raw events table, row by row.

Each one binds its keyword call against the signature its family is declared
with, resolves the connection behind it, and hands the filtered window to the
projection owner beside it. The signatures are the shared ones re-annotated
with what each read returns, so the vocabulary a caller writes stays declared
once while the return type stays readable on the function it belongs to.

Two answers are decided here rather than in SQL. A database that is not
configured -- and no caller-owned connection to fall back on -- yields the
empty model for the read rather than an error, because "not wired up yet" is a
page state and not a failure. A cap of zero and a cleared multiselect are the
same kind of answer earlier still: no row can match, so the read returns
nothing without dialing a connection at all. The one input that *is* rejected
is an unknown `sort_by`, because silently falling back to the default ordering
would hand a caller a differently-ranked table than the one it asked for.
"""

from __future__ import annotations

from typing import Any

from orchestrator.observability.analytics.query.agent_exits import recent_agent_exit_rows
from orchestrator.observability.analytics.query.event_breakdowns import event_breakdown_rows
from orchestrator.observability.analytics.query.filter_options import (
    filter_options_from_rows,
    filter_options_sql,
)
from orchestrator.observability.analytics.query.issue_events import issue_event_rows
from orchestrator.observability.analytics.query.issue_summaries import (
    ISSUE_SORT_BY_OPTIONS,
    SORT_BY_LAST_SEEN,
    issue_summary_rows,
)
from orchestrator.observability.analytics.query.overview_models import (
    DataExtent,
    FilterOptions,
)
from orchestrator.observability.analytics.query.raw_values import empty_filter_selected
from orchestrator.observability.analytics.query.requests import (
    FILTERED_READ_SIGNATURE,
    ISSUES_SIGNATURE,
    ISSUE_EVENTS_SIGNATURE,
    RECENT_EXITS_SIGNATURE,
    SOURCE_READ_SIGNATURE,
    bind_read_request,
    resolve_read_query,
    window_filters,
)
from orchestrator.observability.analytics.query.run_models import (
    AgentExitRow,
    EventBreakdown,
    IssueEventRow,
    IssueSummaryRow,
)


_FILTER_OPTIONS_SIGNATURE = SOURCE_READ_SIGNATURE.replace(
    return_annotation="FilterOptions",
)
_DATA_EXTENT_SIGNATURE = SOURCE_READ_SIGNATURE.replace(
    return_annotation="DataExtent",
)
_EVENT_BREAKDOWN_SIGNATURE = FILTERED_READ_SIGNATURE.replace(
    return_annotation="list[EventBreakdown]",
)
_RECENT_AGENT_EXITS_SIGNATURE = RECENT_EXITS_SIGNATURE.replace(
    return_annotation="list[AgentExitRow]",
)
_ISSUES_READ_SIGNATURE = ISSUES_SIGNATURE.replace(
    return_annotation="list[IssueSummaryRow]",
)
_ISSUE_EVENTS_READ_SIGNATURE = ISSUE_EVENTS_SIGNATURE.replace(
    return_annotation="list[IssueEventRow]",
)


def get_filter_options(*args: Any, **kwargs: Any) -> FilterOptions:
    """Return distinct values populating the dashboard filters."""
    request = bind_read_request(_FILTER_OPTIONS_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return FilterOptions()
    return filter_options_from_rows(query.select(filter_options_sql()))


get_filter_options.__signature__ = _FILTER_OPTIONS_SIGNATURE


def get_data_extent(*args: Any, **kwargs: Any) -> DataExtent:
    """Return the minimum and maximum recorded event timestamps."""
    request = bind_read_request(_DATA_EXTENT_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return DataExtent()
    rows = query.select(
        "SELECT MIN(ts) AS data_min_ts, MAX(ts) AS data_max_ts FROM analytics_events",
    )
    if not rows:
        return DataExtent()
    min_ts, max_ts = rows[0]
    return DataExtent(min_ts=min_ts, max_ts=max_ts)


get_data_extent.__signature__ = _DATA_EXTENT_SIGNATURE


def get_event_breakdown(*args: Any, **kwargs: Any) -> list[EventBreakdown]:
    """Return per-event counts inside the selected window."""
    request = bind_read_request(_EVENT_BREAKDOWN_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return []
    return event_breakdown_rows(query, window_filters(request))


get_event_breakdown.__signature__ = _EVENT_BREAKDOWN_SIGNATURE


def get_recent_agent_exits(
    *args: Any,
    **kwargs: Any,
) -> list[AgentExitRow]:
    """Return the newest filtered agent-exit rows."""
    request = bind_read_request(_RECENT_AGENT_EXITS_SIGNATURE, args, kwargs)
    selected_limit = int(request.options.limit or 0)
    if selected_limit <= 0:
        return []
    query = resolve_read_query(request)
    if not query.available:
        return []
    return recent_agent_exit_rows(
        query,
        window_filters(request),
        selected_limit,
    )


get_recent_agent_exits.__signature__ = _RECENT_AGENT_EXITS_SIGNATURE


def get_issues(*args: Any, **kwargs: Any) -> list[IssueSummaryRow]:
    """Return one aggregate row for each issue in the selected window."""
    request = bind_read_request(_ISSUES_READ_SIGNATURE, args, kwargs)
    sort_by = request.options.sort_by or SORT_BY_LAST_SEEN
    if sort_by not in ISSUE_SORT_BY_OPTIONS:
        raise ValueError(
            f"unknown sort_by {sort_by!r}; expected one of {sorted(ISSUE_SORT_BY_OPTIONS)}",
        )
    selected_limit = int(request.options.limit or 0)
    if selected_limit <= 0:
        return []
    query = resolve_read_query(request)
    if not query.available:
        return []
    return issue_summary_rows(
        query,
        window_filters(request),
        selected_limit,
        sort_by,
    )


get_issues.__signature__ = _ISSUES_READ_SIGNATURE


def get_issue_events(*args: Any, **kwargs: Any) -> list[IssueEventRow]:
    """Return every selected event for one issue, oldest first."""
    request = bind_read_request(_ISSUE_EVENTS_READ_SIGNATURE, args, kwargs)
    filters = request.filters
    if empty_filter_selected(filters.events):
        return []
    if empty_filter_selected(filters.stages):
        return []
    query = resolve_read_query(request)
    if not query.available:
        return []
    return issue_event_rows(
        query,
        window_filters(request, include_identity=False),
        filters.repo,
        filters.issue,
    )


get_issue_events.__signature__ = _ISSUE_EVENTS_READ_SIGNATURE
