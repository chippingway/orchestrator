# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The vocabulary a click on the adoption table is expressed in.

The columns and the two query parameters are spelled out here rather than read
off the owner, because both are a contract with links that already exist: a
sort an operator bookmarked or pasted into a chat names `adopt_sort` and
`adopt_dir` by those spellings, and a column dropped out of the middle of the
set is one of those links quietly reopening the table in its default order. A
case that derived its expectations from the owner would stay green through
either, which is the one thing it must not do.
"""

from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import skill_adoption_columns

# The nine columns in the order an operator reads them across, each with the
# heading it carries and whether it is right-aligned as a number.
_COLUMNS = (
    ("repo", "Repo", False),
    ("role", "Role", False),
    ("backend", "Backend", False),
    ("skill", "Skill", False),
    ("sessions", "Sessions", True),
    ("adopted", "Sessions using skill", True),
    ("rate", "Adoption rate", True),
    ("loads", "Invocation loads", True),
    ("incidental", "Incidental references", True),
)

_NUMERIC_KEYS = frozenset(
    ("sessions", "adopted", "rate", "loads", "incidental"),
)

_SORT_PARAM = "adopt_sort"

_DIR_PARAM = "adopt_dir"


class SkillAdoptionColumnsTest(unittest.TestCase):
    """The column set every heading, link, and ordering is drawn from."""

    def test_the_nine_columns_are_in_order(self) -> None:
        self.assertEqual(
            tuple(
                (column.key, column.label, column.right_aligned)
                for column in skill_adoption_columns.SKILL_ADOPTION_COLUMNS
            ),
            _COLUMNS,
        )

    def test_every_column_is_orderable_by_key(self) -> None:
        # A heading offering a sort the ordering cannot run is a click that
        # reopens the table in its default order.
        self.assertEqual(
            tuple(skill_adoption_columns.SKILL_ADOPTION_SORT_KEYS),
            tuple(key for key, _label, _aligned in _COLUMNS),
        )

    def test_the_counts_are_the_numeric_columns(self) -> None:
        # The two diagnostics are counts like the session pair and the rate
        # between them, so a first click on either opens on its busiest rows.
        self.assertEqual(
            skill_adoption_columns.SKILL_ADOPTION_NUMERIC_KEYS, _NUMERIC_KEYS,
        )


class SkillAdoptionQueryParamsTest(unittest.TestCase):
    """The two spellings a saved sort travels in."""

    def test_the_sort_parameter_is_named(self) -> None:
        self.assertEqual(
            skill_adoption_columns.SKILL_ADOPTION_SORT_PARAM, _SORT_PARAM,
        )

    def test_the_direction_parameter_is_named(self) -> None:
        self.assertEqual(
            skill_adoption_columns.SKILL_ADOPTION_DIR_PARAM, _DIR_PARAM,
        )


if __name__ == "__main__":
    unittest.main()
