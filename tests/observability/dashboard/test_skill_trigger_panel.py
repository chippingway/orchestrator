# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The trigger-rate card a caller reaching past the adoption one still gets.

Nothing in the page pipeline draws this card any more, so what the cases pin is
what such a caller depends on: the two keyword-only shapes it is called
through, the header and aggregate table it leads with, the single notice a
window with no run at all is answered with, the unconditional prompt a window
where nothing triggered carries -- there is no per-session evidence here to
read a genuine no-trigger off -- and the matrix folded collapsed beneath it,
ordered by the query parameters that matrix carries of its own.
"""

from __future__ import annotations

import inspect
import unittest

from orchestrator.observability.dashboard import skill_trigger_panel
from tests.observability.dashboard import skill_matrix_test_support as matrix
from tests.observability.dashboard.skill_panel_test_support import (
    PanelStreamlit,
    all_markup,
    panel_markup,
    rate_row,
)

_TRIGGER_TABLE = "orch-skills"

_MATRIX_TABLE = "orch-skillmatrix"

_MATRIX_FOLD_LABEL = "Per-skill trigger matrix"

_TRACK_SKILL_TRIGGERS = "TRACK_SKILL_TRIGGERS"

_QUIET_COHORT = 0

# The call shape each entry point is reached by, so a caller spelling it the
# way it always has keeps binding.
_KEYWORD_SURFACES = (
    (
        skill_trigger_panel.render_skill_triggers,
        ["st", "skill_rows", "skill_matrix_rows"],
    ),
    (
        skill_trigger_panel.render_skill_matrix_expander,
        ["st", "skill_matrix_rows"],
    ),
)


def _matrix_rows() -> list:
    """Two cells named apart, so an ordering case can locate either."""
    return matrix.cells(
        matrix.CellCase(repo=matrix.REPO_B),
        matrix.CellCase(repo=matrix.REPO_A),
    )


class TriggerPanelSurfaceTest(unittest.TestCase):
    """Both entry points stay keyword-only under their historical names."""

    def test_each_entry_point_binds_by_keyword(self) -> None:
        for entry_point, expected_names in _KEYWORD_SURFACES:
            with self.subTest(entry_point=entry_point.__name__):
                bound = inspect.signature(entry_point).parameters
                self.assertEqual(list(bound), expected_names)
                for name in bound:
                    self.assertEqual(
                        bound[name].kind, inspect.Parameter.KEYWORD_ONLY,
                    )


class TriggerPanelRenderTest(unittest.TestCase):
    """The card leads with the rates and folds the matrix under them."""

    def test_the_card_draws_both_tables(self) -> None:
        page = self._render(rate_row())
        written = all_markup(page)
        self.assertLess(
            written.index("Skill trigger rates"), written.index(_TRIGGER_TABLE),
        )
        self.assertLess(
            written.index(_TRIGGER_TABLE), written.index(_MATRIX_TABLE),
        )
        self.assertEqual(len(page.expanders), 1)
        self.assertIn(_MATRIX_FOLD_LABEL, page.expanders[0].label)
        self.assertFalse(page.expanders[0].expanded)

    def test_a_window_with_no_runs_gets_one_notice(self) -> None:
        page = self._render()
        self.assertEqual(
            page.notices, [skill_trigger_panel.NO_AGENT_EXITS_MESSAGE],
        )
        self.assertEqual(page.markdowns[1:], [])
        self.assertEqual(page.expanders, [])

    def test_a_quiet_window_names_the_switch(self) -> None:
        captions = self._render(rate_row(skill_runs=_QUIET_COHORT)).captions
        self.assertEqual(len(captions), 1)
        self.assertIn(_TRACK_SKILL_TRIGGERS, captions[0])

    def test_a_triggering_window_carries_no_prompt(self) -> None:
        self.assertEqual(self._render(rate_row()).captions, [])

    def _render(self, *skill_rows) -> PanelStreamlit:
        page = PanelStreamlit()
        skill_trigger_panel.render_skill_triggers(
            st=page,
            skill_rows=list(skill_rows),
            skill_matrix_rows=_matrix_rows(),
        )
        return page


class MatrixExpanderTest(unittest.TestCase):
    """The fold-out draws the matrix in the order the page URL named."""

    def test_the_matrix_opens_collapsed(self) -> None:
        page = self._render()
        self.assertEqual(len(page.expanders), 1)
        self.assertIn(_MATRIX_FOLD_LABEL, page.expanders[0].label)
        self.assertFalse(page.expanders[0].expanded)
        self.assertIn(_MATRIX_TABLE, all_markup(page))

    def test_the_matrix_reads_its_own_parameters(self) -> None:
        page = self._render({"mtx_sort": "repo", "mtx_dir": "desc"})
        drawn = panel_markup(page, _MATRIX_TABLE)
        self.assertLess(
            drawn.index(matrix.cell_fragment(matrix.REPO_B)),
            drawn.index(matrix.cell_fragment(matrix.REPO_A)),
        )

    def _render(self, query_params=None) -> PanelStreamlit:
        page = PanelStreamlit(query_params)
        skill_trigger_panel.render_skill_matrix_expander(
            st=page,
            skill_matrix_rows=_matrix_rows(),
        )
        return page


if __name__ == "__main__":
    unittest.main()
