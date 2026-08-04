# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard facade patch-interception tests."""

import unittest


from types import MappingProxyType, SimpleNamespace


from unittest.mock import patch

from orchestrator.observability.dashboard import dispatch

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


ANALYTICS_DB_URL_ENV = "ANALYTICS_DB_URL"


CONFIGURED_DB_URL = "postgresql://h/db"


CONFIGURED_DB_ENV = MappingProxyType({ANALYTICS_DB_URL_ENV: CONFIGURED_DB_URL})


RUN_READ_WAVES_MEMBER = "run_read_waves"


LOG_DASHBOARD_LOAD_MEMBER = "log_dashboard_load"


DRILLDOWN_MEMBER = "_render_drilldown_view"


# What the page's own timer read when a load that found nothing started, and
# the first wave it had already spent by then.
LOAD_START = 12.5


FIRST_WAVE = (("summary", object()), ("prev_summary", object()))


class _QuietStreamlit:
    """Minimal fake `st` for the empty-window renderer to draw its banner on.

    Only the surface that renderer touches is implemented, as a no-op, so a
    render runs without the optional Streamlit.
    """

    # `info` is Streamlit's own name for the banner an empty window is
    # answered with, so the stand-in has to spell it the same way.
    def info(self, *args, **kwargs) -> None:  # noqa: WPS110
        """No-op stand-in for `st.info`."""


class FacadePatchInterceptionTest(unittest.TestCase):
    """The page pipeline resolves its siblings through the
    `orchestrator.dashboard` facade at call time -- and its read
    waves on the dashboard owner that drives them -- so a `patch.object` on
    either intercepts the running pipeline (mirroring the `workflow`
    stage-handler facade). Identity re-export alone would not catch a stubbed
    rebind, so these drive the callers under a patch.
    """

    def test_patched_run_read_waves_drives_data_load(self) -> None:
        # `_load_dashboard_data` reaches the read-wave dispatch on its owner,
        # so a patched `dispatch.run_read_waves` supplies the data.
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        read_results = {"summary": object()}
        kpis = object()
        with patch.object(
            dispatch,
            RUN_READ_WAVES_MEMBER,
            return_value=(read_results, kpis),
        ) as stub:
            loaded = dashboard._load_dashboard_data(
                SimpleNamespace(st=object()),
                SimpleNamespace(reads=object()),
            )
            stub.assert_called_once()
        self.assertIs(loaded.read_results, read_results)
        self.assertIs(loaded.kpis, kpis)

    def test_empty_window_logs_its_first_wave(self) -> None:
        # A short-circuited load never reaches the line `run_read_waves` ends
        # on, so the banner that ended it measures the load instead -- off the
        # plan's own clock, the reads it had already spent, and the way they
        # were issued. Counting both waves here would report ten reads nobody
        # paid for on every empty window.
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        page = SimpleNamespace(
            reads=SimpleNamespace(
                started_at=LOAD_START,
                first_wave=list(FIRST_WAVE),
                parallel=True,
            ),
            controls=SimpleNamespace(filters=object()),
        )
        with (
            patch.object(dispatch, LOG_DASHBOARD_LOAD_MEMBER) as logged,
            patch.object(dashboard, DRILLDOWN_MEMBER),
        ):
            dashboard._render_empty_window(
                SimpleNamespace(st=_QuietStreamlit()), page,
            )
            logged.assert_called_once_with(
                load_start=LOAD_START,
                reads=len(FIRST_WAVE),
                parallel=True,
            )

    def test_patched_sections_drive_page_render(self) -> None:
        # `_render_dashboard_widgets` reaches both wave renderers through the
        # facade, so patched stubs run in place of the real sections.
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        calls: list[str] = []
        with (
            patch.object(
                dashboard,
                "_render_chart_widgets",
                side_effect=lambda *args: calls.append("chart"),
            ),
            patch.object(
                dashboard,
                "_render_remaining_widgets",
                side_effect=lambda *args: calls.append("remaining"),
            ),
        ):
            dashboard._render_dashboard_widgets(object(), object(), object())
        self.assertEqual(calls, ["chart", "remaining"])
