# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable trajectory HTML surface backed by the trajectory-viewer owners.

The one module the page reaches every builder through, defining none of them.
Each name is the owner's own object under the spelling this surface published
it as, and the one shape published from here -- the KPI tile -- is stamped with
this module by the owner that defines it.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import (
    css,
    run_html,
    summary_html,
    timeline_html,
    usage_html,
)


_TimelineUsagePair = timeline_html.TimelineUsagePair
EXTRA_CSS = css.EXTRA_CSS
_USAGE_SEP = usage_html.USAGE_SEPARATOR
_REPO_LABEL = run_html.REPO_LABEL
_card_header_html = summary_html.card_header_html
_topbar_html = summary_html.topbar_html
_fmt_cost_usd = summary_html.fmt_cost_usd
_TrajectoryKpi = summary_html._TrajectoryKpi
_trajectory_kpis = summary_html.trajectory_kpis
_trajectory_kpi_html = summary_html.trajectory_kpi_html
_kpi_strip_html = summary_html.kpi_strip_html
_meta_html = run_html.meta_html
_labeled_chips_html = run_html.labeled_chips_html
_run_table_row_html = run_html.run_table_row_html
_runs_table_html = run_html.runs_table_html
_BADGE_BY_KIND = timeline_html.BADGE_BY_KIND
_FIXTURE_LABEL_PREFIX = run_html.FIXTURE_LABEL_PREFIX
_timeline_entry_html = timeline_html.timeline_entry_html
_usage_chip = usage_html.usage_chip
_run_usage_chips = usage_html.run_usage_chips
_run_usage_note = usage_html.run_usage_note
_run_usage_html = usage_html.run_usage_html
_turn_usage_html = usage_html.turn_usage_html
_timeline_with_usage = timeline_html.timeline_with_usage
_run_picker_label = run_html.run_picker_label
