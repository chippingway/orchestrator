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


DASHBOARD_MODULE = "orchestrator.dashboard"


DASHBOARD_CARDS_MODULE = "orchestrator.dashboard_cards"


DASHBOARD_KPI_STRIP_MODULE = "orchestrator.dashboard_kpi_strip"


DASHBOARD_READS_MODULE = "orchestrator.dashboard_reads"


DASHBOARD_WIDGETS_MODULE = "orchestrator.dashboard_widgets"


DASHBOARD_STATE_MODULE = "orchestrator.dashboard_state"


_RELOAD_POP_MODULES = (
    "orchestrator.config",
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


class _MainSourceTest(unittest.TestCase):
    """Base for source checks over the lazy entrypoint and page helpers.

    Streamlit / Plotly are opt-in (not installed for the default
    `uv sync --locked`), so these read the rendered function source
    rather than driving the page under Streamlit. The entrypoint loads
    optional modules lazily and delegates the metadata load, the
    no-data state, and the staged render beneath it to named helpers,
    so `_source_of` fetches the boundary each assertion protects.
    """

    def _main_source(self) -> str:
        return self._source_of(ENTRYPOINT_ATTR)

    def _source_of(self, name: str) -> str:
        _, dashboard = _reload(CONFIGURED_DB_ENV)
        return inspect.getsource(getattr(dashboard, name))


class MainRenderDispatchTest(_MainSourceTest):
    """`main` reaches its branches through named helpers, not inline."""

    def test_read_and_error_paths_use_helpers(self) -> None:
        # `main` dispatches the metadata load and the no-data branch
        # through focused helpers rather than inlining the cached
        # wrappers, the fan-out, the load log, and the banners. Which
        # panel the staged render below then draws, and in what order,
        # is the dashboard owners' and pinned beside them.
        for helper, marker in (
            ("_run_dashboard", "read_static_metadata("),
            ("_render_dashboard", "page_states.render_no_data("),
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
