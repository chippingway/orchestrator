# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the topbar and KPI strip, answered by its owner.

Each name is the owner's own object under the spelling this module published
it as, so what a caller renders the banner and the five tiles with is decided
once rather than per import site.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import summary_html


_TrajectoryKpi = summary_html._TrajectoryKpi
_card_header_html = summary_html.card_header_html
_topbar_html = summary_html.topbar_html
_fmt_cost_usd = summary_html.fmt_cost_usd
_trajectory_kpis = summary_html.trajectory_kpis
_trajectory_kpi_html = summary_html.trajectory_kpi_html
_kpi_strip_html = summary_html.kpi_strip_html
