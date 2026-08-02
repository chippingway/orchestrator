# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard first-wave render and fan-out error propagation tests."""

import inspect


import unittest


from functools import partial


from types import MappingProxyType


from tests.dashboard_reload_helpers import (
    reload_dashboard as _reload,
    load_analytics_read as _analytics_read_module,
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


ENTRYPOINT_ATTR = "main"


RENDER_FIRST_WAVE_MEMBER = "_render_first_wave"


def _raise_read_error(
    message: str,
    calls: list[str] | None = None,
    call_name: str | None = None,
) -> None:
    read_error = _analytics_read_module().AnalyticsReadError
    if calls is None or call_name is None:
        raise read_error(message)
    calls.append(call_name)
    raise read_error(message)


class _MainSourceTest(unittest.TestCase):
    """Base for source checks over the lazy entrypoint and page helpers.

    Streamlit / Plotly are opt-in (not installed for the default
    `uv sync --locked`), so these read the rendered function source
    rather than driving the page under Streamlit. The entrypoint loads
    optional modules lazily and the page pipeline delegates controls,
    read waves, empty states, and widget sections to named helpers, so
    `_source_of` fetches the boundary each assertion protects.
    """

    def _main_source(self) -> str:
        return self._source_of(ENTRYPOINT_ATTR)

    def _source_of(self, name: str) -> str:
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        return inspect.getsource(getattr(dashboard, name))

    def _assert_source_order(self, member_name: str, markers: tuple[str, ...]) -> None:
        source = self._source_of(member_name)
        indexes = [source.index(marker) for marker in markers]
        self.assertEqual(indexes, sorted(indexes))

    def _source_tail(self, source: str, start: str) -> str:
        return source[source.index(start):]


class FirstWaveRenderTest(_MainSourceTest):
    """What the page draws off the first wave, while the second is still out.

    Which reads each wave is made of is the read-plan owner's and how the two
    are driven around this render is the dispatch owner's; both are pinned
    beside them. What is left here is what the page puts on screen in between.
    """

    def test_the_chrome_and_kpi_strip_render(self) -> None:
        first_render_source = self._source_of(RENDER_FIRST_WAVE_MEMBER)
        self.assertIn("_render_topbar_and_meta(", first_render_source)
        self.assertIn("_kpi_strip_html(", first_render_source)
        topbar_source = self._source_of("_render_topbar_and_meta")
        self.assertIn("topbar_slot.markdown(", topbar_source)
        self.assertIn("meta_slot.markdown(", topbar_source)

    def test_an_empty_window_draws_no_kpis(self) -> None:
        # Reporting nothing back is what the dispatch short-circuits the second
        # wave on, so a window with no events has to leave through the banner
        # rather than fall on through to the KPI strip.
        first_wave_source = self._source_of(RENDER_FIRST_WAVE_MEMBER)
        self._assert_source_order(
            RENDER_FIRST_WAVE_MEMBER,
            ("summary.total_events == 0", "_render_empty_window("),
        )
        self.assertIn(
            "return None",
            self._source_tail(first_wave_source, "summary.total_events == 0"),
        )


class FanOutReadsErrorPropagationTest(unittest.TestCase):
    """A failed read reaches the caller off the fan-out the facade publishes.

    Both waves of a load are dispatched through it, and the caller answers a
    failure with one banner, so neither branch may collect an
    `AnalyticsReadError` as a result among the results.
    """

    def test_sequential_propagates_in_staged_call(self) -> None:
        _, dashboard = _reload()
        read_error = _analytics_read_module().AnalyticsReadError

        with self.assertRaisesRegex(read_error, "first wave dead"):
            dashboard._fan_out_reads(
                [("summary", partial(_raise_read_error, "first wave dead"))],
                parallel=False,
            )

    def test_parallel_propagates_in_staged_call(self) -> None:
        _, dashboard = _reload()
        read_error = _analytics_read_module().AnalyticsReadError

        with self.assertRaisesRegex(read_error, "second wave dead"):
            dashboard._fan_out_reads(
                [("repo_rows", partial(_raise_read_error, "second wave dead"))],
                parallel=True,
                max_workers=2,
            )
