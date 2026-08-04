# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable KPI-strip surface over the owners that shape it.

The window totals a tile reports, the per-day lines drawn beneath them, and the
four display entries they are assembled into are the dashboard owners' own
objects. Every historical `dashboard.<name>` import resolved through this
module reaches those rather than a copy of any of them, so a tile a caller
renders and the number the owner computed cannot differ.

The render pass that actually builds the strip names `kpi_strip` directly, so
this surface is what a caller reaching past that owner lands on rather than a
step on the page's own path.
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
