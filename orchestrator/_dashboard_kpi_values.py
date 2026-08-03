# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the KPI totals and the tiles built from them.

The window reduced to the scalars a tile reports, the four display entries and
the keys they are read back by, and the build that returns them beside the
throughput pair are the dashboard owner's own objects. A caller that names this
module reaches those rather than a copy, so a page and the owner cannot report
a window differently.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import kpi_strip


_LABEL_KEY = kpi_strip._LABEL_KEY
_VALUE_KEY = kpi_strip._VALUE_KEY
_DELTA_KEY = kpi_strip._DELTA_KEY
_SUBTITLE_KEY = kpi_strip._SUBTITLE_KEY
_SPARK_KEY = kpi_strip._SPARK_KEY
_KpiStripData = kpi_strip.KpiStripData
_KpiInputs = kpi_strip.KpiInputs
_KpiTotals = kpi_strip.KpiTotals
_kpi_totals = kpi_strip.kpi_totals
_cost_per_resolved = kpi_strip.cost_per_resolved
_kpi_strip_entries = kpi_strip.kpi_strip_entries
_build_kpi_strip_data = kpi_strip.build_kpi_strip_data
