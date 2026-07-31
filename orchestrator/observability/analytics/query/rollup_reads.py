# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The seven reads answered off the day-bucketed rollup rather than the events.

Each one binds its keyword call against the signature its family is declared
with, resolves the connection behind it, and hands the filtered window to the
projection owner beside it. Every signature is the shared filtered one
re-annotated with what the read returns, so the vocabulary a caller writes
stays declared once while the return type stays readable on the function it
belongs to.

A window bounded by whole days is what these seven have in common, and what
lets them scan the rollup instead of the events table: a page framing a window
asks for totals, a comparison against the window before it, a daily series, and
the stage, backend, repository, and throughput breakdowns across it -- none of
which needs a row's own timestamp.

Two answers are decided here rather than in SQL. A database that is not
configured -- and no caller-owned connection to fall back on -- yields the
empty model for the read rather than an error, because "not wired up yet" is a
page state and not a failure. And a backend comparison is about finished runs,
so an event selection that excludes `agent_exit` returns nothing without
dialing: the pinned filter under it could never match.
"""

from __future__ import annotations

from typing import Any

from orchestrator.observability.analytics.query.activity_models import ThroughputDayRow
from orchestrator.observability.analytics.query.backend_efficiency import (
    backend_efficiency_rows,
)
from orchestrator.observability.analytics.query.conditions import agent_event_excluded
from orchestrator.observability.analytics.query.cost_models import (
    BackendEfficiencyRow,
    RepoBreakdownRow,
)
from orchestrator.observability.analytics.query.kpi_totals import kpi_prev_summary
from orchestrator.observability.analytics.query.overview_models import (
    Summary,
    TimeSeriesPoint,
)
from orchestrator.observability.analytics.query.repo_breakdowns import repo_breakdown_rows
from orchestrator.observability.analytics.query.requests import (
    FILTERED_READ_SIGNATURE,
    bind_read_request,
    resolve_read_query,
    window_filters,
)
from orchestrator.observability.analytics.query.run_models import StageBreakdown
from orchestrator.observability.analytics.query.stage_breakdowns import (
    stage_breakdown_rows,
)
from orchestrator.observability.analytics.query.summary_queries import query_summary_rows
from orchestrator.observability.analytics.query.summary_results import summary_from_rows
from orchestrator.observability.analytics.query.throughput_days import throughput_rows
from orchestrator.observability.analytics.query.time_series import time_series_rows


_SUMMARY_SIGNATURE = FILTERED_READ_SIGNATURE.replace(
    return_annotation="Summary",
)
_KPI_PREVIOUS_SIGNATURE = FILTERED_READ_SIGNATURE.replace(
    return_annotation="Summary",
)
_TIME_SERIES_SIGNATURE = FILTERED_READ_SIGNATURE.replace(
    return_annotation="list[TimeSeriesPoint]",
)
_STAGE_BREAKDOWN_SIGNATURE = FILTERED_READ_SIGNATURE.replace(
    return_annotation="list[StageBreakdown]",
)
_BACKEND_EFFICIENCY_SIGNATURE = FILTERED_READ_SIGNATURE.replace(
    return_annotation="list[BackendEfficiencyRow]",
)
_REPO_BREAKDOWN_SIGNATURE = FILTERED_READ_SIGNATURE.replace(
    return_annotation="list[RepoBreakdownRow]",
)
_THROUGHPUT_SIGNATURE = FILTERED_READ_SIGNATURE.replace(
    return_annotation="list[ThroughputDayRow]",
)


def get_summary(*args: Any, **kwargs: Any) -> Summary:
    """Return aggregate counts for the selected reporting window."""
    request = bind_read_request(_SUMMARY_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return Summary()
    return summary_from_rows(
        query_summary_rows(query, window_filters(request)),
    )


get_summary.__signature__ = _SUMMARY_SIGNATURE


def get_kpi_prev(*args: Any, **kwargs: Any) -> Summary:
    """Return previous-window scalar totals used by KPI comparisons."""
    request = bind_read_request(_KPI_PREVIOUS_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return Summary()
    return kpi_prev_summary(query, window_filters(request))


get_kpi_prev.__signature__ = _KPI_PREVIOUS_SIGNATURE


def get_time_series(*args: Any, **kwargs: Any) -> list[TimeSeriesPoint]:
    """Return daily event, cost, and token aggregates."""
    request = bind_read_request(_TIME_SERIES_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return []
    return time_series_rows(query, window_filters(request))


get_time_series.__signature__ = _TIME_SERIES_SIGNATURE


def get_stage_breakdown(*args: Any, **kwargs: Any) -> list[StageBreakdown]:
    """Return per-stage activity and cost aggregates."""
    request = bind_read_request(_STAGE_BREAKDOWN_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return []
    return stage_breakdown_rows(query, window_filters(request))


get_stage_breakdown.__signature__ = _STAGE_BREAKDOWN_SIGNATURE


def get_backend_efficiency(
    *args: Any,
    **kwargs: Any,
) -> list[BackendEfficiencyRow]:
    """Return per-backend agent-run efficiency aggregates."""
    request = bind_read_request(_BACKEND_EFFICIENCY_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return []
    if agent_event_excluded(request.filters.events):
        return []
    return backend_efficiency_rows(query, window_filters(request))


get_backend_efficiency.__signature__ = _BACKEND_EFFICIENCY_SIGNATURE


def get_repo_breakdown(*args: Any, **kwargs: Any) -> list[RepoBreakdownRow]:
    """Return per-repository activity aggregates."""
    request = bind_read_request(_REPO_BREAKDOWN_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return []
    return repo_breakdown_rows(query, window_filters(request))


get_repo_breakdown.__signature__ = _REPO_BREAKDOWN_SIGNATURE


def get_throughput_breakdown(
    *args: Any,
    **kwargs: Any,
) -> list[ThroughputDayRow]:
    """Return daily resolved and rejected issue counts."""
    request = bind_read_request(_THROUGHPUT_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return []
    return throughput_rows(query, window_filters(request))


get_throughput_breakdown.__signature__ = _THROUGHPUT_SIGNATURE
