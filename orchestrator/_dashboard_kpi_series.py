# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the per-day KPI series.

The two token totals, the throughput pair, and the per-day cost, token, and
resolved lines a sparkline is drawn from are the dashboard owner's own objects.
A caller that names this module reaches those rather than a copy, so a tile and
the line beneath it cannot be counted two different ways.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import kpi_series


_summary_total_tokens = kpi_series.summary_total_tokens
_time_series_total_tokens = kpi_series.time_series_total_tokens
_throughput_totals = kpi_series.throughput_totals
_daily_point_totals = kpi_series.daily_point_totals
_DailyKpiSeries = kpi_series.DailyKpiSeries
_daily_kpi_series = kpi_series.daily_kpi_series
