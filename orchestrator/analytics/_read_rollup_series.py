# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical KPI / daily-series import site, answered by the query owners.

The four names are the two owners' own functions, so the trimmed scalar scan a
KPI comparison reads back, and the per-`(day, event)` cell a chart pivots, are
decided once whichever module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.kpi_totals import (
    kpi_prev_sql as _kpi_prev_sql,
    kpi_prev_summary as _kpi_prev_summary,
)
from orchestrator.observability.analytics.query.time_series import (
    time_series_from_row as _time_series_from_row,
    time_series_rows as _time_series_rows,
)


_COMPATIBILITY_EXPORTS = (
    _kpi_prev_sql,
    _kpi_prev_summary,
    _time_series_from_row,
    _time_series_rows,
)
