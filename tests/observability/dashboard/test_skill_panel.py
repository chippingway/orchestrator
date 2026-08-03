# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The card a window's skill adoption is reported on.

The cases name what the card decides rather than what the four tables under it
draw: which panel leads and which folds away, the single notice a window with
no run at all is answered with, the order each table is opened in when the page
URL asked for one, and the caption that qualifies a quiet window. That caption
is the reading with the most to get wrong, so every evidence shape a window
with no adopting session can arrive in is here -- each one proof that tracking
recorded something, and so a window the card must not tell an operator to
switch tracking on for.

Whether the window carried adoption evidence is also what the diagnostics
beneath are handed, so the two windows that flag separates -- a genuine
no-trigger and one nobody enabled tracking for -- are driven through the card
rather than through the diagnostics directly.
"""

from __future__ import annotations

import unittest
from typing import Mapping, Optional

from orchestrator.observability.dashboard import skill_panel
from tests.observability.dashboard import skill_matrix_test_support as matrix
from tests.observability.dashboard.skill_adoption_test_support import (
    CellCase,
    REPO_A,
    REPO_B,
    cell_fragment,
    cells,
)
from tests.observability.dashboard.skill_panel_test_support import (
    PanelStreamlit,
    all_markup,
    panel_markup,
    rate_row,
)

_ADOPTION_TABLE = "orch-skilladopt"

_TRIGGER_TABLE = "orch-skills"

_MATRIX_TABLE = "orch-skillmatrix"

_ENABLE_LABEL = "Enable"

_TRACK_SKILL_TRIGGERS = "TRACK_SKILL_TRIGGERS"

_QUIET_COHORT = 0

# Every evidence shape a window with no adopting session can arrive in, and the
# words the caption has to reach for. Availability alone reads as the genuine
# zero it is; without it the caption names whichever of the two diagnostics the
# window did record, so an operator can match it against those columns.
_CAPTION_CASES = (
    (CellCase(sessions=5, adopted=0), ("genuine 0% adoption",)),
    (CellCase(sessions=0, adopted=0, incidental=1), ("incidental",)),
    (CellCase(sessions=0, adopted=0, load_rows=2), ("loaded",)),
    (
        CellCase(sessions=0, adopted=0, load_rows=2, incidental=1),
        ("loaded", "incidental"),
    ),
)


def _render_card(
    *cases: CellCase,
    skill_runs: int = 2,
    with_runs: bool = True,
    query_params: Optional[Mapping[str, str]] = None,
) -> PanelStreamlit:
    """Draw the whole card for those adoption cells onto a fake page."""
    page = PanelStreamlit(query_params)
    skill_panel.render_skill_adoption(
        st=page,
        skill_adoption_rows=cells(*cases),
        skill_rows=[rate_row(skill_runs=skill_runs)] if with_runs else [],
        skill_matrix_rows=matrix.cells(
            matrix.CellCase(repo=matrix.REPO_B),
            matrix.CellCase(repo=matrix.REPO_A),
        ),
    )
    return page


class SkillCardLayoutTest(unittest.TestCase):
    """Adoption leads the card; the invocation views fold under it."""

    def test_adoption_is_drawn_before_the_fold(self) -> None:
        page = _render_card(CellCase())
        written = all_markup(page)
        self.assertLess(
            written.index("Skill adoption"), written.index(_ADOPTION_TABLE),
        )
        self.assertLess(
            written.index(_ADOPTION_TABLE), written.index(_TRIGGER_TABLE),
        )
        self.assertLess(
            written.index(_TRIGGER_TABLE), written.index(_MATRIX_TABLE),
        )

    def test_the_invocation_views_open_collapsed(self) -> None:
        fold = _render_card(CellCase()).expanders
        self.assertEqual(len(fold), 1)
        self.assertIn("Invocation-level diagnostics", fold[0].label)
        self.assertFalse(fold[0].expanded)

    def test_a_window_with_no_runs_gets_one_notice(self) -> None:
        # The whole card is answered once rather than each of its four tables
        # drawing an empty state of its own.
        page = _render_card(with_runs=False)
        self.assertEqual(len(page.notices), 1)
        self.assertIn("No `agent_exit` rows", page.notices[0])
        self.assertEqual(page.markdowns[1:], [])
        self.assertEqual(page.expanders, [])

    def test_each_table_reads_its_own_parameters(self) -> None:
        # The two tables carry separate parameters precisely so a click on one
        # leaves the other's order alone, so the card has to read each table's
        # own pair back rather than one for both.
        page = _render_card(
            CellCase(repo=REPO_A),
            CellCase(repo=REPO_B),
            query_params={"adopt_sort": "repo", "adopt_dir": "desc"},
        )
        adoption = panel_markup(page, _ADOPTION_TABLE)
        self.assertLess(
            adoption.index(cell_fragment(REPO_B)),
            adoption.index(cell_fragment(REPO_A)),
        )
        drawn = panel_markup(page, _MATRIX_TABLE)
        self.assertLess(
            drawn.index(matrix.cell_fragment(matrix.REPO_A)),
            drawn.index(matrix.cell_fragment(matrix.REPO_B)),
        )


class SkillAdoptionCaptionTest(unittest.TestCase):
    """A quiet window is qualified, never told to switch tracking on."""

    def test_each_evidence_shape_is_named_neutrally(self) -> None:
        for case, expected_words in _CAPTION_CASES:
            with self.subTest(case=case):
                captions = _render_card(case).captions
                self.assertEqual(len(captions), 1)
                for word in expected_words:
                    self.assertIn(word, captions[0])
                self.assertNotIn(_ENABLE_LABEL, captions[0])
                self.assertNotIn(_TRACK_SKILL_TRIGGERS, captions[0])

    def test_a_loaded_window_is_not_incidental(self) -> None:
        # Loads and incidental references are separate columns, so a window
        # carrying only the first must not be captioned as the second.
        case = CellCase(sessions=0, adopted=0, load_rows=2)
        self.assertNotIn("Only incidental", _render_card(case).captions[0])

    def test_an_adopting_window_is_left_unqualified(self) -> None:
        # Nothing about a window where sessions adopted and runs triggered is
        # worth qualifying, so neither the card nor the fold under it captions.
        adopting = CellCase(sessions=5, adopted=3)
        self.assertEqual(_render_card(adopting).captions, [])

    def test_a_window_with_no_cells_defers(self) -> None:
        # The table already renders the notice naming the switch, and saying it
        # twice would read as two separate problems.
        page = _render_card()
        self.assertEqual(page.captions, [])
        empty = panel_markup(page, f"{_ADOPTION_TABLE}-empty")
        self.assertIn(_TRACK_SKILL_TRIGGERS, empty)


class SkillDiagnosticsHandoffTest(unittest.TestCase):
    """Adoption evidence is what the diagnostics read the quiet case by."""

    def test_evidence_makes_a_quiet_window_genuine(self) -> None:
        page = _render_card(
            CellCase(sessions=5, adopted=0), skill_runs=_QUIET_COHORT,
        )
        written = " ".join(page.captions)
        self.assertIn("No agent run triggered a skill", written)
        self.assertNotIn(_ENABLE_LABEL, written)
        self.assertNotIn(_TRACK_SKILL_TRIGGERS, written)

    def test_no_evidence_names_the_switch(self) -> None:
        captions = _render_card(skill_runs=_QUIET_COHORT).captions
        self.assertEqual(len(captions), 1)
        self.assertIn(_ENABLE_LABEL, captions[0])
        self.assertIn(_TRACK_SKILL_TRIGGERS, captions[0])


if __name__ == "__main__":
    unittest.main()
