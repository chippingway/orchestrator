# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The panel each repository's loaded skills are reported in.

The cases name what the panel itself decides rather than what the columns,
ordering, headers, or row projection beneath it do: that a window with no
session evidence renders a notice instead of a table, what that notice says,
and that the rows reach the table already ordered -- the clicked column when
the page URL named one, and the repository-then-rate default when it did not.
"""

from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import skill_adoption
from tests.observability.dashboard.skill_adoption_test_support import (
    REPO_A,
    REPO_B,
    SKILL_BETA,
    SKILL_GAMMA,
    CellCase,
    cell_fragment,
    rendered,
)

_SORT_KEY_SESSIONS = "sessions"

# A cohort the skill was offered to more widely than the shared default's, so a
# case can order two cells by the count they differ in.
_BUSY_SESSIONS = 9

# Two cells of one repository whose rates differ, so the default order's second
# key is exercised alongside its first.
_HOT_ADOPTED = 3

_EMPTY_NOTICE_CLASS = "orch-skilladopt-empty"

_TABLE_OPENING = "<table"

_ESCAPED_APOSTROPHE = "&#x27;"


class SkillAdoptionEmptyWindowTest(unittest.TestCase):
    """What a window with no session evidence renders instead."""

    def test_the_notice_replaces_the_table(self) -> None:
        notice = skill_adoption.skill_adoption_html([])
        self.assertIn(_EMPTY_NOTICE_CLASS, notice)
        self.assertNotIn(_TABLE_OPENING, notice)

    def test_the_notice_names_the_switch(self) -> None:
        # A panel nobody turned tracking on for would otherwise read as a bug
        # on a page opened to find out which skills were used.
        self.assertIn(
            "TRACK_SKILL_TRIGGERS", skill_adoption.skill_adoption_html([]),
        )

    def test_the_notice_is_escaped(self) -> None:
        self.assertIn(
            _ESCAPED_APOSTROPHE, skill_adoption.skill_adoption_html([]),
        )


class SkillAdoptionOrderingTest(unittest.TestCase):
    """The rows reach the table in the order the page asked for."""

    def test_an_unsorted_table_opens_on_the_default(self) -> None:
        # Repository ascending, then adoption rate descending inside it, so
        # the skills a repository's sessions actually loaded lead its rows.
        markup = rendered(
            CellCase(repo=REPO_B),
            CellCase(skill=SKILL_BETA),
            CellCase(skill=SKILL_GAMMA, adopted=_HOT_ADOPTED),
        )
        self.assertLess(
            markup.index(cell_fragment(SKILL_GAMMA)),
            markup.index(cell_fragment(SKILL_BETA)),
        )
        self.assertLess(
            markup.index(cell_fragment(REPO_A)),
            markup.index(cell_fragment(REPO_B)),
        )

    def test_a_clicked_column_reorders_the_rows(self) -> None:
        cases = (CellCase(repo=REPO_B), CellCase(sessions=_BUSY_SESSIONS))
        ascending = rendered(*cases, sort_key=_SORT_KEY_SESSIONS)
        self.assertLess(
            ascending.index(cell_fragment(REPO_B)),
            ascending.index(cell_fragment(REPO_A)),
        )
        descending = rendered(
            *cases, sort_key=_SORT_KEY_SESSIONS, descending=True,
        )
        self.assertLess(
            descending.index(cell_fragment(REPO_A)),
            descending.index(cell_fragment(REPO_B)),
        )


if __name__ == "__main__":
    unittest.main()
