# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the four sections beneath the hero card.

The paired lifecycle bars, the ranking of a window's costliest issues beside
the backends that ran them, the repository spend beside the run-health tiles,
and the activity grid under all three are the dashboard owners' own renders. A
caller that names this module -- or the widget hub above it -- gets those
rather than a copy, so the section an operator reads and the one a fix under
the owners reaches cannot report the same window two ways. The height both
bars are pinned to and the notice a window with no `agent_exit` row is
answered with come from the same owners, under the spellings the page always
imported them by.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import (
    activity_panel,
    issue_cost_panel,
    reliability_panel,
    stage_cost_panel,
)


_TABLE_ROW_HEIGHT = stage_cost_panel.TABLE_ROW_HEIGHT
_TABLE_BASE_HEIGHT = stage_cost_panel.TABLE_BASE_HEIGHT
NO_AGENT_EXITS_MESSAGE = issue_cost_panel.NO_AGENT_EXITS_MESSAGE
_render_stage_review_bars = stage_cost_panel.render_stage_review_bars
_paired_bars_height = stage_cost_panel.paired_bars_height
_render_issues_and_backends = issue_cost_panel.render_issues_and_backends
_render_repo_and_reliability = reliability_panel.render_repo_and_reliability
_render_activity_heatmap = activity_panel.render_activity_heatmap
