# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the state a page render is threaded through.

The seven shapes this module is named for are the dashboard owner's own
classes, published here under the private spellings the widget pipeline always
imported them by. A caller that names this module gets those rather than
copies, so a section handed a page and a section that builds one cannot end up
typed against two different windows.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import page_models


_DashboardModules = page_models.DashboardModules
_DashboardFilters = page_models.DashboardFilters
_DashboardControls = page_models.DashboardControls
_DashboardPage = page_models.DashboardPage
_DashboardKpis = page_models.DashboardKpis
_LoadedDashboard = page_models.LoadedDashboard
_ReliabilityPanelData = page_models.ReliabilityPanelData
