# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable trajectory HTML surface backed by focused rendering leaves."""
from __future__ import annotations

from orchestrator import _dashboard_compatibility as compatibility
from orchestrator import _trajectory_dashboard_timeline_html as timeline
from orchestrator import _trajectory_dashboard_usage_html as usage
from orchestrator.observability.trajectory_viewer import css, run_html, summary_html


_TimelineUsagePair = timeline.TimelineUsagePair
EXTRA_CSS = css.EXTRA_CSS
_USAGE_SEP = usage.USAGE_SEPARATOR
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
_BADGE_BY_KIND = timeline.BADGE_BY_KIND
_FIXTURE_LABEL_PREFIX = run_html.FIXTURE_LABEL_PREFIX
_timeline_entry_html = timeline._timeline_entry_html
_usage_chip = usage._usage_chip
_run_usage_chips = usage._run_usage_chips
_run_usage_note = usage._run_usage_note
_run_usage_html = usage._run_usage_html
_turn_usage_html = usage._turn_usage_html
_timeline_with_usage = timeline._timeline_with_usage
_run_picker_label = run_html.run_picker_label

# The timeline and usage builders report this module, which is the one surface
# the page reaches every builder through, so the split behind it stays private.
# The owners under `trajectory_viewer/` report themselves -- a function's
# module is the owner that defines it -- and the one shape published from here,
# the KPI tile, is stamped by its own owner.
_COMPATIBILITY_MEMBERS = (
    _timeline_entry_html,
    _usage_chip,
    _run_usage_chips,
    _run_usage_note,
    _run_usage_html,
    _turn_usage_html,
    _timeline_with_usage,
)
compatibility.preserve_defining_module(__name__, _COMPATIBILITY_MEMBERS)
