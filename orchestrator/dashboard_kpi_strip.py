# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable KPI-strip surface over the owners that shape it.

The window totals a tile reports, the per-day lines drawn beneath them, and the
four display entries they are assembled into are the dashboard owners' own
objects. The widget pipeline that builds the strip, and every historical
`dashboard.<name>` import resolved through this module, reach those rather than
a copy of any of them, so a tile a page renders and the number the owner
computed cannot differ.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import kpi_series, kpi_strip


_KpiStripData = kpi_strip.KpiStripData
_summary_total_tokens = kpi_series.summary_total_tokens
_time_series_total_tokens = kpi_series.time_series_total_tokens
_throughput_totals = kpi_series.throughput_totals
_daily_point_totals = kpi_series.daily_point_totals
_DailyKpiSeries = kpi_series.DailyKpiSeries
_daily_kpi_series = kpi_series.daily_kpi_series
_KpiInputs = kpi_strip.KpiInputs
_KpiTotals = kpi_strip.KpiTotals
_kpi_totals = kpi_strip.kpi_totals
_cost_per_resolved = kpi_strip.cost_per_resolved
_kpi_strip_entries = kpi_strip.kpi_strip_entries
_build_kpi_strip_data = kpi_strip.build_kpi_strip_data
