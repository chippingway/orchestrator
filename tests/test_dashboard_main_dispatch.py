# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard main-render dispatch, fan-out, and metadata wiring tests."""

import inspect


import unittest


from types import MappingProxyType


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


ENTRYPOINT_ATTR = "main"


RENDER_FIRST_WAVE_MEMBER = "_render_first_wave"


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


class MainRenderDispatchTest(_MainSourceTest):
    """The page pipeline preserves control and widget render order."""

    def test_render_helpers_called_in_page_order(self) -> None:
        self._assert_source_order(
            "_render_dashboard_controls",
            ("_render_sidebar_filters(", "_render_date_filter_bar("),
        )
        self._assert_source_order(
            "_render_chart_widgets",
            (
                "_render_hero_usage(",
                "_render_stage_review_bars(",
                "_render_issues_and_backends(",
                "_render_repo_and_reliability(",
                "_render_activity_heatmap(",
            ),
        )
        self._assert_source_order(
            "_render_remaining_widgets",
            (
                "_render_skill_adoption(",
                "_render_recent_runs(",
                "_render_drilldown_view(",
                "_render_dashboard_footer(",
            ),
        )
        self._assert_source_order(
            "_render_dashboard_widgets",
            ("_render_chart_widgets(", "_render_remaining_widgets("),
        )

    def test_read_and_error_paths_use_helpers(self) -> None:
        # `main` dispatches the staged read fan-out and the empty /
        # error rendering branches through focused helpers rather than
        # inlining the cached wrappers, the fan-out, the load log, and
        # the metadata / no-data / empty-window banners.
        for helper, marker in (
            ("_run_dashboard", "read_static_metadata("),
            ("_render_dashboard", "_render_no_data("),
            ("_prepare_dashboard_page", "read_plan.widget_readers("),
            ("_load_dashboard_data", "dispatch.run_read_waves("),
            (RENDER_FIRST_WAVE_MEMBER, "_render_empty_window("),
        ):
            with self.subTest(helper=helper, marker=marker):
                self.assertIn(marker, self._source_of(helper))
        # The read-error banners and the cached wrappers belong to the
        # helpers, so `main` never inlines `st.error(`, a
        # `_fan_out_reads` call, or a `_read_*` wrapper definition.
        main_src = self._main_source()
        self.assertNotIn("st.error(", main_src)
        self.assertNotIn("_fan_out_reads(", main_src)
        self.assertNotIn("def _read_summary(", main_src)


class MainParallelFanOutWiringTest(_MainSourceTest):
    """The page decides which way its reads are issued and starts the clock
    they are measured against, both while it prepares the load. What that
    decision then costs is the dispatch owner's, and pinned beside it.
    Streamlit is not installed for the default `uv sync --locked`, so these
    inspect the rendered sources rather than driving the page under Streamlit.
    """

    def test_main_drives_parallel_off_env_helper(self) -> None:
        src = self._source_of("_prepare_dashboard_page")
        # The env-backed helper is the single source of truth for the
        # flag so a test or shutdown hook can flip it without
        # rewriting `main()`.
        self.assertIn("dashboard_parallel_reads_enabled()", src)

    def test_main_stamps_the_load_clock(self) -> None:
        # The `dashboard.load:` line reports the whole wait an operator sat
        # through, so the timer starts where the page starts preparing the
        # load rather than where the first wave is dispatched.
        self.assertIn(
            "perf_counter()",
            self._source_of("_prepare_dashboard_page"),
        )


class StaticMetadataDispatchTest(_MainSourceTest):
    """The page opens on the metadata owner's cached pair, not the raw reads.

    `get_data_extent` and `get_filter_options` are the two reads no filter
    narrows, so they belong behind the wrappers that cache them for the whole
    ingest cycle rather than inline where a rerun would re-issue them.
    """

    def test_the_page_opens_through_the_metadata_load(self) -> None:
        run_src = self._source_of("_run_dashboard")
        self.assertIn("read_static_metadata(", run_src)
        self.assertNotIn("get_data_extent(", run_src)
        self.assertNotIn("get_filter_options(", run_src)
