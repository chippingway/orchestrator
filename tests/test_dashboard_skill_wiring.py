# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard skill-matrix, adoption, and metadata wiring tests."""

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


SECOND_WAVE_READERS_MEMBER = "_second_wave_readers"


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


class SkillMatrixWiringTest(_MainSourceTest):
    """The invocation-level per-skill trigger matrix rides the same cached
    / fan-out read pattern as every other widget (its wrapper lives in
    `_widget_readers`) and renders as the second table inside the
    invocation-level diagnostics expander, beneath the session-adoption
    matrix. Streamlit is not installed for the default sync, so these
    inspect the rendered sources rather than driving the page under
    Streamlit.
    """

    def test_matrix_dispatched_in_second_wave(self) -> None:
        src = self._source_of(SECOND_WAVE_READERS_MEMBER)
        self.assertIn(
            '_widget_task(st, "skill_matrix_rows", _read_skill_trigger_matrix, key)',
            src,
        )

    def test_matrix_is_second_diagnostic_table(self) -> None:
        # Inside the diagnostics expander the matrix is the SECOND table:
        # it renders after the aggregate `_skill_triggers_html(skill_rows)`
        # trigger-rate table.
        src = self._source_of("_render_skill_invocation_diagnostics")
        agg = src.index("_skill_triggers_html(skill_rows)")
        matrix = src.index("_skill_matrix_html(")
        self.assertLess(agg, matrix)

    def test_diagnostics_in_collapsed_expander(self) -> None:
        # The invocation-level views fold into a collapsed expander
        # (mirroring the "Recent agent runs" block) so they do not dominate
        # the card beneath the primary adoption matrix. Both the aggregate
        # table and the matrix render after an `st.expander(...,
        # expanded=False)` clearly named an invocation-level diagnostic.
        src = self._source_of("_render_skill_invocation_diagnostics")
        expander = src.index('with st.expander(\n        "Invocation-level')
        aggregate = src.index("_skill_triggers_html(")
        matrix = src.index("_skill_matrix_html(")
        self.assertLess(expander, aggregate)
        self.assertLess(expander, matrix)
        # The expander block carrying the diagnostics opens collapsed.
        block = src[expander:matrix]
        self.assertIn("expanded=False", block)


class SkillAdoptionWiringTest(_MainSourceTest):
    """The primary per-session skill-adoption matrix rides the same cached
    / fan-out read pattern as every other widget (its wrapper lives in
    `_widget_readers`) and renders as the headline table of the skill
    panel, above the invocation-level diagnostics. Streamlit is not
    installed for the default sync, so these inspect the rendered sources
    rather than driving the page under Streamlit.
    """

    def test_adoption_dispatched_in_second_wave(self) -> None:
        src = self._source_of(SECOND_WAVE_READERS_MEMBER)
        self.assertIn(
            '_widget_task(st, "skill_adoption_rows", _read_skill_adoption, key)',
            src,
        )

    def test_adoption_is_primary_render(self) -> None:
        # The session-adoption matrix is the headline table: it renders
        # before the invocation-level diagnostics expander, inside the same
        # card.
        src = self._source_of("_render_skill_adoption")
        adoption = src.index("_skill_adoption_html(")
        diagnostics = src.index("_render_skill_invocation_diagnostics(")
        self.assertLess(adoption, diagnostics)

    def test_adoption_needs_aggregate_rows(self) -> None:
        # The adoption render sits after the empty early return, so a window
        # with no `agent_exit` rows shows the single notice rather than an
        # empty-state per table.
        src = self._source_of("_render_skill_adoption")
        branch = src.index("if not skill_rows:")
        else_branch = src.index(
            'st.info("No `agent_exit` rows match the current filters.")',
            branch,
        )
        adoption = src.index("_skill_adoption_html(")
        self.assertLess(branch, adoption)
        self.assertLess(else_branch, adoption)


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
