# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the page draws under the figures, and the whole second wave in order.

The cards a window's figures are drawn on stack above; these are the four
things beneath them, and the order is again the page's argument. The skill card
reports what the runs behind those figures were working with, the run listing
is the rows every reading above it was reduced from, the per-issue trace is the
narrowing an operator opens one of those runs into, and the footer restates the
span and the run count all of it was measured over -- so it is last, and it is
the only one of the four that is not a panel.

``render_dashboard_widgets`` is the whole second wave in one call: the figure
cards, then these. Splitting the page's order across two calls is what lets a
caller draw either half against a stand-in, and keeping the pair here is what
keeps the order itself in one readable place.

Each section is named on its own owner rather than resolved off the flat facade
at call time, so a test intercepting one patches the module that draws it.
Streamlit, pandas, and the theme are the caller's, carried in the modules
shape, so importing this owner needs neither optional dependency.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import (
    chart_sections,
    drilldown,
    page_models,
    page_states,
    recent_runs,
    skill_panel,
)


def render_remaining_widgets(
    modules: page_models.DashboardModules,
    page: page_models.DashboardPage,
    loaded: page_models.LoadedDashboard,
) -> None:
    """Draw the panels beneath the figure cards, and sign the page off."""
    read_results = loaded.read_results
    skill_panel.render_skill_adoption(
        st=modules.st,
        skill_adoption_rows=read_results["skill_adoption_rows"],
        skill_rows=read_results["skill_rows"],
        skill_matrix_rows=read_results["skill_matrix_rows"],
    )
    recent_runs.render_recent_runs(
        st=modules.st,
        pd=modules.pd,
        agent_exits=read_results["agent_exits"],
        tz_offset_choice=page.controls.timezone_offset,
    )
    drilldown.render_drilldown_view(modules, page.controls.filters)
    page_states.render_dashboard_footer(
        modules,
        page.controls.filters,
        read_results["summary"],
    )


def render_dashboard_widgets(
    modules: page_models.DashboardModules,
    page: page_models.DashboardPage,
    loaded: page_models.LoadedDashboard,
) -> None:
    """Draw everything the second wave answered for, in page order."""
    chart_sections.render_chart_widgets(modules, page, loaded)
    render_remaining_widgets(modules, page, loaded)
