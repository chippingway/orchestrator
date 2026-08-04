# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the top of the page and the load it opens.

The selections the sidebar comes back with, the offset a run is displayed in,
the filters those selections normalize into, the controls the whole top of the
page is read back as, and the staged plan the panels below are drawn from are
the dashboard owner's own objects, published here under the private spellings
the page always imported them by. A caller that names this module gets those
rather than copies, so the window an operator narrowed and the keys the reads
were bound to cannot come apart.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import page_controls


_SidebarSelections = page_controls.SidebarSelections
_timezone_choice = page_controls.timezone_choice
_resolve_dashboard_filters = page_controls.resolve_dashboard_filters
_render_dashboard_controls = page_controls.render_dashboard_controls
_prepare_dashboard_page = page_controls.prepare_dashboard_page
_render_sidebar_filters = page_controls.render_sidebar_filters
