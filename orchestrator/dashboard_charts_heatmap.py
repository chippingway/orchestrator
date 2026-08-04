# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the weekday-by-hour activity heatmap.

The 7x24 figure, the cells it is drawn from, the weekday labels and hour span
those cells are shaped by, and the layout that squares them off are the charts
owner's own objects. `orchestrator.dashboard_charts` re-exports
`hour_weekday_heatmap` from here under its original name, so the grid a caller
reaches through that hub and the grid the activity card draws off the owner
cannot be two figures that merely agree.
"""
from __future__ import annotations

from orchestrator.observability.dashboard.charts import heatmap


_HOURS_PER_DAY = heatmap.HOURS_PER_DAY
_WEEKDAY_LABELS = heatmap.WEEKDAY_LABELS
_heatmap_layout = heatmap.heatmap_layout
_heatmap_matrix = heatmap.heatmap_matrix
_valid_heatmap_point = heatmap.valid_heatmap_point
hour_weekday_heatmap = heatmap.hour_weekday_heatmap
