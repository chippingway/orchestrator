# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the horizontal cost panel and its bars.

The margin a ranking is gutter'd by, the frame it is laid out in, and the
request one series of bars is described by are the charts owner's own objects.
The generic, per-stage, and per-review-round leaves that name this module reach
those rather than a copy, so the three families cannot be framed one way here
and another under the owner.
"""
from __future__ import annotations

from orchestrator.observability.dashboard.charts import cost_layout


HORIZONTAL_BAR_MARGIN = cost_layout.HORIZONTAL_BAR_MARGIN
_HorizontalCostLayout = cost_layout.HorizontalCostLayout
_apply_horizontal_cost_layout = cost_layout.apply_horizontal_cost_layout
_CostBarTrace = cost_layout.CostBarTrace
_cost_bar_trace = cost_layout.cost_bar_trace
