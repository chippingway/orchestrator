# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the row a date filter is laid out in.

The five slots the bar is drawn across, the label naming it in the first, the
three presets offered in the second, and the position the current one is
preselected at are the dashboard owner's own objects. A caller that names this
module gets those rather than a copy, so the bar a page renders and the layout
the owner decides cannot come apart.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import date_controls


_DateFilterColumns = date_controls.DateFilterColumns
_date_filter_columns = date_controls.date_filter_columns
_render_date_filter_label = date_controls.render_date_filter_label
_preset_radio_index = date_controls.preset_radio_index
_render_preset_choice = date_controls.render_preset_choice
