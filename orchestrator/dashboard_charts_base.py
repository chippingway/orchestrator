# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the shared chart primitives.

The no-data placeholder, the money / monospace / two-line-tick labels, the
list reversal, and the horizontal-bar height and legend -- with the row and
extra heights that sizing is measured in -- are the charts owner's own
objects. The usage and cost leaves that name this module reach those rather
than a copy, so a panel's empty state, its bar labels, and its height cannot
be answered one way here and another under the owner.
"""
from __future__ import annotations

from orchestrator.observability.dashboard.charts import primitives


_HORIZONTAL_BAR_ROW_HEIGHT = primitives.HORIZONTAL_BAR_ROW_HEIGHT
_HORIZONTAL_BAR_EXTRA_HEIGHT = primitives.HORIZONTAL_BAR_EXTRA_HEIGHT
_empty_figure = primitives.empty_figure
_horizontal_legend = primitives.horizontal_legend
_horizontal_panel_height = primitives.horizontal_panel_height
_money_text = primitives.money_text
_monospace_textfont = primitives.monospace_textfont
_reverse_lists = primitives.reverse_lists
_two_line_y_ticks = primitives.two_line_y_ticks
