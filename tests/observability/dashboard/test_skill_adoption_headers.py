# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The header row where every column is also the adoption table's sort control.

The cases name what a click on one heading offers and what the row says about
where the table already stands: the link each column writes, the direction an
untouched column starts from, and the single arrow the active column carries
and reverses. A sort control that opened a second tab is here too, because the
filters the table was narrowed by live in the page it would leave behind.

The columns and the parameters a link is written with are spelled out rather
than read off the owner, so a heading dropped from the row or a parameter
renamed under it fails here instead of passing against whatever the owner now
holds.
"""

from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import skill_adoption_headers

_ASCENDING = "asc"

_DESCENDING = "desc"

# The nine columns in the order an operator reads them across, each with the
# heading it carries and the direction a first click on it means: the
# interesting end of a count is the busiest row, and of a name the top of the
# alphabet.
_COLUMNS = (
    ("repo", "Repo", _ASCENDING),
    ("role", "Role", _ASCENDING),
    ("backend", "Backend", _ASCENDING),
    ("skill", "Skill", _ASCENDING),
    ("sessions", "Sessions", _DESCENDING),
    ("adopted", "Sessions using skill", _DESCENDING),
    ("rate", "Adoption rate", _DESCENDING),
    ("loads", "Invocation loads", _DESCENDING),
    ("incidental", "Incidental references", _DESCENDING),
)

_SORT_PARAM = "adopt_sort"

_DIR_PARAM = "adopt_dir"

_SORT_KEY_SESSIONS = "sessions"

_SORT_KEY_REPO = "repo"

_ARROW_SPAN = '<span class="orch-skilladopt-sort">'

_ARROW_DOWN = f"{_ARROW_SPAN}▼</span>"

_ARROW_UP = f"{_ARROW_SPAN}▲</span>"

_SAME_TAB = 'target="_self"'


def _link(column_key: str, direction: str) -> str:
    """The selection a click on `column_key` writes into the page URL."""
    return f'href="?{_SORT_PARAM}={column_key}&{_DIR_PARAM}={direction}"'


def _unsorted_header_html() -> str:
    """The row a table nobody has clicked yet is headed by."""
    return skill_adoption_headers.skill_adoption_header_html(None, False)


class SkillAdoptionHeaderRowTest(unittest.TestCase):
    """What an untouched header row offers."""

    def test_the_nine_headings_are_in_order(self) -> None:
        markup = _unsorted_header_html()
        positions = [
            markup.index(f">{label}</a>") for _key, label, _dir in _COLUMNS
        ]
        self.assertEqual(positions, sorted(positions))

    def test_a_sort_stays_in_the_clicked_page(self) -> None:
        self.assertIn(_SAME_TAB, _unsorted_header_html())

    def test_a_first_click_counts_down_names_up(self) -> None:
        markup = _unsorted_header_html()
        for column_key, _label, direction in _COLUMNS:
            with self.subTest(column=column_key):
                self.assertIn(_link(column_key, direction), markup)

    def test_no_column_is_marked_before_a_click(self) -> None:
        self.assertNotIn(_ARROW_SPAN, _unsorted_header_html())


class SkillAdoptionActiveHeaderTest(unittest.TestCase):
    """What the row says once one column is the one the rows are in."""

    def test_only_the_active_column_carries_an_arrow(self) -> None:
        markup = skill_adoption_headers.skill_adoption_header_html(
            _SORT_KEY_SESSIONS, True,
        )
        self.assertEqual(markup.count(_ARROW_SPAN), 1)

    def test_the_active_column_shows_and_reverses(self) -> None:
        descending = skill_adoption_headers.skill_adoption_header_html(
            _SORT_KEY_SESSIONS, True,
        )
        self.assertIn(_ARROW_DOWN, descending)
        self.assertIn(_link(_SORT_KEY_SESSIONS, _ASCENDING), descending)
        ascending = skill_adoption_headers.skill_adoption_header_html(
            _SORT_KEY_REPO, False,
        )
        self.assertIn(_ARROW_UP, ascending)
        self.assertIn(_link(_SORT_KEY_REPO, _DESCENDING), ascending)


if __name__ == "__main__":
    unittest.main()
