# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the page's two-wave render pipeline.

The chrome and strip drawn between the waves, the load staged around them, the
five figure cards, the panels beneath them, and the single call the whole
second wave is drawn by are the dashboard owners' own functions, published here
under the private spellings the page always imported them by. A caller that
names this module gets those rather than copies, so what an operator reads and
what a fix under the owner reaches are one render.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import (
    chart_sections,
    page_pipeline,
    page_sections,
)


_render_topbar_and_meta = page_pipeline.render_topbar_and_meta
_render_dashboard_insights = page_pipeline.render_dashboard_insights
_render_first_wave = page_pipeline.render_first_wave
_load_dashboard_data = page_pipeline.load_dashboard_data
_render_chart_widgets = chart_sections.render_chart_widgets
_render_remaining_widgets = page_sections.render_remaining_widgets
_render_dashboard_widgets = page_sections.render_dashboard_widgets
