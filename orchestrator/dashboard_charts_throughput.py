# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the per-day throughput strip.

The resolved-per-day bars, the calendar a window's days are filled in from,
the series those days and counts arrive as, and the height the strip is
pinned to are the charts owner's own objects. `orchestrator.dashboard_charts`
re-exports `done_per_day_bars` from here under its original name, so the strip
a caller reaches through that hub and the strip the reliability panel draws off
the owner cannot be two figures that merely agree.
"""
from __future__ import annotations

from orchestrator.observability.dashboard.charts import throughput


_THROUGHPUT_CHART_HEIGHT = throughput.THROUGHPUT_CHART_HEIGHT
_ThroughputSeries = throughput.ThroughputSeries
_calendar_days = throughput.calendar_days
_throughput_series = throughput.throughput_series
done_per_day_bars = throughput.done_per_day_bars
