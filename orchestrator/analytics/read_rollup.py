# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical rollup-read import site, answered by the query owners.

The seven reads are the owners' own functions, so a call made here runs the
SQL, the ordering, and the short circuits the rollup families are maintained
by. The underscored names beside them are the projections, fragments, and cell
readings this hub published while it owned them: a private name a caller
already imported is still a name it imported, so each is bound to the owner's
object rather than re-derived here.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.backend_efficiency import (
    backend_efficiency_from_row as _backend_efficiency_from_row,
    backend_efficiency_rows as _backend_efficiency_rows,
    backend_efficiency_sql as _backend_efficiency_sql,
)
from orchestrator.observability.analytics.query.cache_shares import (
    ROLLUP_ALL_TOKENS_SQL as _ROLLUP_ALL_TOKENS_SQL,
    ROLLUP_CACHE_FRACTION_SQL as _ROLLUP_CACHE_FRACTION_SQL,
    ROLLUP_CACHE_TOKENS_SQL as _ROLLUP_CACHE_TOKENS_SQL,
)
from orchestrator.observability.analytics.query.kpi_totals import (
    kpi_prev_sql as _kpi_prev_sql,
    kpi_prev_summary as _kpi_prev_summary,
)
from orchestrator.observability.analytics.query.raw_values import (
    float_or_none as _float_or_none,
)
from orchestrator.observability.analytics.query.repo_breakdowns import (
    repo_breakdown_rows as _repo_breakdown_rows,
)
from orchestrator.observability.analytics.query.rollup_reads import (
    get_backend_efficiency as get_backend_efficiency,
    get_kpi_prev as get_kpi_prev,
    get_repo_breakdown as get_repo_breakdown,
    get_stage_breakdown as get_stage_breakdown,
    get_summary as get_summary,
    get_throughput_breakdown as get_throughput_breakdown,
    get_time_series as get_time_series,
)
from orchestrator.observability.analytics.query.row_cells import (
    cost_cell as _cost_cell,
    day_value as _day_value,
    row_value as _row_value,
)
from orchestrator.observability.analytics.query.stage_breakdowns import (
    stage_breakdown_from_row as _stage_breakdown_from_row,
    stage_breakdown_rows as _stage_breakdown_rows,
    stage_breakdown_sql as _stage_breakdown_sql,
)
from orchestrator.observability.analytics.query.summary_queries import (
    build_summary_sql as _build_summary_sql,
    build_summary_where as _build_summary_where,
    query_summary_rows as _query_summary_rows,
)
from orchestrator.observability.analytics.query.summary_results import (
    SUMMARY_TOTAL_FIELD_CASTS as _SUMMARY_TOTAL_FIELD_CASTS,
    ordered_summary_counts as _ordered_summary_counts,
    summary_count_order as _summary_count_order,
    summary_from_rows as _summary_from_rows,
    summary_total_values as _summary_total_values,
    summary_totals_row as _summary_totals_row,
)
from orchestrator.observability.analytics.query.throughput_days import (
    THROUGHPUT_RESOLVED_STAGES as _THROUGHPUT_RESOLVED_STAGES,
    selected_throughput_stages as _selected_throughput_stages,
    throughput_from_row as _throughput_from_row,
    throughput_rows as _throughput_rows,
)
from orchestrator.observability.analytics.query.time_series import (
    time_series_from_row as _time_series_from_row,
    time_series_rows as _time_series_rows,
)


_COMPATIBILITY_EXPORTS = (
    _backend_efficiency_from_row,
    _backend_efficiency_rows,
    _backend_efficiency_sql,
    _stage_breakdown_from_row,
    _stage_breakdown_rows,
    _stage_breakdown_sql,
    _ROLLUP_ALL_TOKENS_SQL,
    _ROLLUP_CACHE_FRACTION_SQL,
    _ROLLUP_CACHE_TOKENS_SQL,
    _THROUGHPUT_RESOLVED_STAGES,
    _repo_breakdown_rows,
    _selected_throughput_stages,
    _throughput_from_row,
    _throughput_rows,
    _kpi_prev_sql,
    _kpi_prev_summary,
    _time_series_from_row,
    _time_series_rows,
    _cost_cell,
    _day_value,
    _float_or_none,
    _row_value,
    _build_summary_sql,
    _build_summary_where,
    _query_summary_rows,
    _SUMMARY_TOTAL_FIELD_CASTS,
    _ordered_summary_counts,
    _summary_count_order,
    _summary_from_rows,
    _summary_total_values,
    _summary_totals_row,
    get_backend_efficiency,
    get_kpi_prev,
    get_repo_breakdown,
    get_stage_breakdown,
    get_summary,
    get_throughput_breakdown,
    get_time_series,
)
