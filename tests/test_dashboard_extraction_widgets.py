# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard widget extraction tests."""

import sys


import unittest


from types import MappingProxyType


from tests.dashboard_reload_helpers import (
    reload_dashboard as _reload,
)


DASHBOARD_WIDGETS_MODULE = "orchestrator.dashboard_widgets"


ANALYTICS_DB_URL_ENV = "ANALYTICS_DB_URL"


CONFIGURED_DB_URL = "postgresql://h/db"


CONFIGURED_DB_ENV = MappingProxyType({ANALYTICS_DB_URL_ENV: CONFIGURED_DB_URL})


DASHBOARD_OWNERS = "orchestrator.observability.dashboard"


ACTIVITY_PANEL_OWNER = f"{DASHBOARD_OWNERS}.activity_panel"


ISSUE_COST_PANEL_OWNER = f"{DASHBOARD_OWNERS}.issue_cost_panel"


PAGE_MODELS_OWNER = f"{DASHBOARD_OWNERS}.page_models"


RECENT_RUNS_OWNER = f"{DASHBOARD_OWNERS}.recent_runs"


RELIABILITY_PANEL_OWNER = f"{DASHBOARD_OWNERS}.reliability_panel"


SKILL_PANEL_OWNER = f"{DASHBOARD_OWNERS}.skill_panel"


SKILL_TRIGGER_PANEL_OWNER = f"{DASHBOARD_OWNERS}.skill_trigger_panel"


STAGE_COST_PANEL_OWNER = f"{DASHBOARD_OWNERS}.stage_cost_panel"


USAGE_PANEL_OWNER = f"{DASHBOARD_OWNERS}.usage_panel"


# Each member the hub publishes and the module that defines it. The widget
# sections still living on the hub report it; the page-state shapes, the two
# skill cards, the two cost-comparison panels, the repository-spend and
# reliability pair and the activity grid beneath them, the recent-run listing,
# and the
# hero usage card report the owners under
# `observability/` that hold them, since a claim here would move an owner's own
# object off the owner that defines it.
_WIDGET_MEMBER_HOMES = MappingProxyType({
    "_DashboardModules": PAGE_MODELS_OWNER,
    "_DashboardFilters": PAGE_MODELS_OWNER,
    "_DashboardControls": PAGE_MODELS_OWNER,
    "_DashboardPage": PAGE_MODELS_OWNER,
    "_backend_tokens_by_day": USAGE_PANEL_OWNER,
    "_load_dashboard_data": DASHBOARD_WIDGETS_MODULE,
    "_render_topbar_and_meta": DASHBOARD_WIDGETS_MODULE,
    "_render_first_wave": DASHBOARD_WIDGETS_MODULE,
    "_render_chart_widgets": DASHBOARD_WIDGETS_MODULE,
    "_render_remaining_widgets": DASHBOARD_WIDGETS_MODULE,
    "_render_dashboard_widgets": DASHBOARD_WIDGETS_MODULE,
    "_render_dashboard_footer": DASHBOARD_WIDGETS_MODULE,
    "_render_no_data": DASHBOARD_WIDGETS_MODULE,
    "_render_empty_window": DASHBOARD_WIDGETS_MODULE,
    "_render_hero_usage": USAGE_PANEL_OWNER,
    "_render_stage_review_bars": STAGE_COST_PANEL_OWNER,
    "_render_issues_and_backends": ISSUE_COST_PANEL_OWNER,
    "_render_repo_and_reliability": RELIABILITY_PANEL_OWNER,
    "_render_activity_heatmap": ACTIVITY_PANEL_OWNER,
    "_render_skill_adoption": SKILL_PANEL_OWNER,
    "_render_skill_invocation_diagnostics": SKILL_PANEL_OWNER,
    "_render_skill_triggers": SKILL_TRIGGER_PANEL_OWNER,
    "_render_skill_matrix_expander": SKILL_TRIGGER_PANEL_OWNER,
    "_render_recent_runs": RECENT_RUNS_OWNER,
    "_render_drilldown_view": DASHBOARD_WIDGETS_MODULE,
})


_WIDGETS_FACADE_CONSTANTS = (
    "PLOTLY_CONFIG",
    "NO_DATA_MESSAGE",
    "EMPTY_WINDOW_MESSAGE",
)


class WidgetRenderingExtractionTest(unittest.TestCase):
    """The widget-rendering pipeline -- the two-wave render passes, the
    empty / no-data states, the per-issue drill-down renderer, and the page
    footer -- lives in
    `orchestrator.dashboard_widgets`, and `orchestrator.dashboard`
    re-exports the members the page pipeline and these tests reach under
    the same names so the `dashboard.<name>` surface keeps resolving to the
    same object. The KPI-strip aggregations live under
    `observability/dashboard/` -- `kpi_series` for the per-day lines and
    `kpi_strip` for the tiles drawn over them -- and are reached through
    `orchestrator.dashboard_kpi_strip` (`KpiStripExtractionTest`); the two
    skill cards live there too -- `skill_panel` for the adoption card and the
    diagnostics folded under it, `skill_trigger_panel` for the trigger-rate one
    beside them -- as do the three cost-comparison sections -- `stage_cost_panel`
    for the paired lifecycle bars and the height they share,
    `issue_cost_panel` for the ranked issues beside the backends that ran
    them, and `reliability_panel` for the repository ranking beside the tiles
    and days those runs are read for -- the weekday-by-hour grid closing that
    run of sections, under `activity_panel`, the recent-run listing above that
    drill-down, under
    `recent_runs`, the hero spend and token-usage card the page opens with,
    under `usage_panel`, the shapes the pipeline threads, under `page_models`,
    and the Plotly defaults its figures are drawn under, in `render_config`,
    and all of them are reached through this hub.
    """

    def test_widget_members_report_their_home(self) -> None:
        _reload(CONFIGURED_DB_ENV)
        widgets = sys.modules[DASHBOARD_WIDGETS_MODULE]
        for name, home in _WIDGET_MEMBER_HOMES.items():
            with self.subTest(name=name):
                self.assertEqual(getattr(widgets, name).__module__, home)

    def test_facade_reexports_widgets_objects(self) -> None:
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        widgets = sys.modules[DASHBOARD_WIDGETS_MODULE]
        for name in (*_WIDGET_MEMBER_HOMES, *_WIDGETS_FACADE_CONSTANTS):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(dashboard, name),
                    f"dashboard dropped the historical {name!r} alias",
                )
                self.assertIs(getattr(dashboard, name), getattr(widgets, name))
