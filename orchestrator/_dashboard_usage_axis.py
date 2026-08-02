# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the usage chart's aligned axes.

The step count both axes are cut into, the height the hero panel is pinned to,
the rounding that gives each axis a maximum it divides into equal steps, and
the layout the token and cost scales are assembled in are the charts owner's
own objects. The figure leaf that names this module reaches those rather than a
copy, so the range a stack is drawn against and the range its axis is labelled
from cannot come apart.
"""
from __future__ import annotations

from orchestrator.observability.dashboard.charts import usage_axis


USAGE_CHART_HEIGHT = usage_axis.USAGE_CHART_HEIGHT
USAGE_GRID_STEPS = usage_axis.USAGE_GRID_STEPS
_nice_axis_max = usage_axis.nice_axis_max
_usage_axis_ranges = usage_axis.usage_axis_ranges
_usage_layout = usage_axis.usage_layout
