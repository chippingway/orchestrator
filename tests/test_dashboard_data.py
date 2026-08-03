# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard data-preparation and Plotly tests."""

import unittest


from datetime import date


from tests.dashboard_reload_helpers import (
    reload_dashboard as _reload,
)


SKIP_DOTENV_ENV = "ORCHESTRATOR_SKIP_DOTENV"


TOKEN_FILE_ENV = "ORCHESTRATOR_TOKEN_FILE"


MISSING_TOKEN_FILE = "/tmp/agent-orchestrator-token-missing"


ANALYTICS_READ_MODULE = "orchestrator.analytics.read"


DASHBOARD_MODULE = "orchestrator.dashboard"


DASHBOARD_CARDS_MODULE = "orchestrator.dashboard_cards"


DASHBOARD_KPI_STRIP_MODULE = "orchestrator.dashboard_kpi_strip"


DASHBOARD_READS_MODULE = "orchestrator.dashboard_reads"


DASHBOARD_WIDGETS_MODULE = "orchestrator.dashboard_widgets"


DASHBOARD_STATE_MODULE = "orchestrator.dashboard_state"


_RELOAD_POP_MODULES = (
    "orchestrator.config",
    ANALYTICS_READ_MODULE,
    "orchestrator.analytics",
    DASHBOARD_STATE_MODULE,
    "orchestrator.dashboard_kpis",
    "orchestrator.dashboard_html",
    DASHBOARD_CARDS_MODULE,
    DASHBOARD_KPI_STRIP_MODULE,
    "orchestrator.dashboard_skill_adoption",
    "orchestrator.dashboard_skill_matrix",
    DASHBOARD_READS_MODULE,
    DASHBOARD_WIDGETS_MODULE,
    DASHBOARD_MODULE,
)


_YEAR = 2026


MAY01 = date(_YEAR, 5, 1)


MAY07 = date(_YEAR, 5, 7)


BACKEND_CLAUDE = "claude"


BACKEND_CODEX = "codex"


class DashboardDataPrepTest(unittest.TestCase):
    """Small data-prep helpers keep `main()` focused on render sequencing."""

    def test_backend_day_tokens_sum_duplicate_cells(self) -> None:
        _, dashboard = _reload()
        from orchestrator.analytics.read import BackendDailyTokensRow

        rows = [
            BackendDailyTokensRow(day=MAY01, backend=BACKEND_CLAUDE, total_tokens=10),
            BackendDailyTokensRow(day=MAY01, backend=BACKEND_CLAUDE, total_tokens=5),
            BackendDailyTokensRow(day=MAY01, backend=BACKEND_CODEX, total_tokens=3),
            BackendDailyTokensRow(day=MAY07, backend=BACKEND_CLAUDE, total_tokens=8),
        ]

        self.assertEqual(
            dashboard._backend_tokens_by_day(rows),
            {
                MAY01: {BACKEND_CLAUDE: 15.0, BACKEND_CODEX: 3.0},
                MAY07: {BACKEND_CLAUDE: 8.0},
            },
        )


class PlotlyConfigTest(unittest.TestCase):
    """`PLOTLY_CONFIG` is passed to every `st.plotly_chart` so the
    hover modebar (camera / zoom / pan) stays off every card --
    the standalone mock has no chart chrome.
    """

    def test_plotly_config_disables_modebar(self) -> None:
        _, dashboard = _reload()
        self.assertEqual(dashboard.PLOTLY_CONFIG.get("displayModeBar"), False)
