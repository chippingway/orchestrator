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


RECENT_RUNS_OWNER = f"{DASHBOARD_OWNERS}.recent_runs"


SKILL_PANEL_OWNER = f"{DASHBOARD_OWNERS}.skill_panel"


SKILL_TRIGGER_PANEL_OWNER = f"{DASHBOARD_OWNERS}.skill_trigger_panel"


# Each member the hub publishes and the module that defines it. The widget
# sections still living on the hub report it; the two skill cards and the
# recent-run listing report the owners under `observability/` that hold them,
# since a claim here would move an owner's own function off the owner that
# defines it.
_WIDGET_MEMBER_HOMES = MappingProxyType({
    "_DashboardModules": DASHBOARD_WIDGETS_MODULE,
    "_DashboardFilters": DASHBOARD_WIDGETS_MODULE,
    "_DashboardControls": DASHBOARD_WIDGETS_MODULE,
    "_DashboardPage": DASHBOARD_WIDGETS_MODULE,
    "_backend_tokens_by_day": DASHBOARD_WIDGETS_MODULE,
    "_load_dashboard_data": DASHBOARD_WIDGETS_MODULE,
    "_render_topbar_and_meta": DASHBOARD_WIDGETS_MODULE,
    "_render_first_wave": DASHBOARD_WIDGETS_MODULE,
    "_render_chart_widgets": DASHBOARD_WIDGETS_MODULE,
    "_render_remaining_widgets": DASHBOARD_WIDGETS_MODULE,
    "_render_dashboard_widgets": DASHBOARD_WIDGETS_MODULE,
    "_render_dashboard_footer": DASHBOARD_WIDGETS_MODULE,
    "_render_no_data": DASHBOARD_WIDGETS_MODULE,
    "_render_empty_window": DASHBOARD_WIDGETS_MODULE,
    "_render_hero_usage": DASHBOARD_WIDGETS_MODULE,
    "_render_stage_review_bars": DASHBOARD_WIDGETS_MODULE,
    "_render_issues_and_backends": DASHBOARD_WIDGETS_MODULE,
    "_render_repo_and_reliability": DASHBOARD_WIDGETS_MODULE,
    "_render_activity_heatmap": DASHBOARD_WIDGETS_MODULE,
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
    empty / no-data states, the per-issue drill-down renderer, the page
    footer, and the page-state dataclasses the pipeline threads -- lives in
    `orchestrator.dashboard_widgets`, and `orchestrator.dashboard`
    re-exports the members the page pipeline and these tests reach under
    the same names so the `dashboard.<name>` surface keeps resolving to the
    same object. The KPI-strip aggregations live under
    `observability/dashboard/` -- `kpi_series` for the per-day lines and
    `kpi_strip` for the tiles drawn over them -- and are reached through
    `orchestrator.dashboard_kpi_strip` (`KpiStripExtractionTest`); the two
    skill cards live there too -- `skill_panel` for the adoption card and the
    diagnostics folded under it, `skill_trigger_panel` for the trigger-rate one
    beside them -- as does the recent-run listing above that drill-down, under
    `recent_runs`, and all three are reached through this hub.
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
