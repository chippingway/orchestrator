# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The vocabulary a click on the trigger matrix is expressed in.

The columns and the two query parameters are spelled out here rather than read
off the owner, because both are a contract with links that already exist: a
sort an operator bookmarked or pasted into a chat names `mtx_sort` and
`mtx_dir` by those spellings, and a column dropped out of the middle of the set
is one of those links quietly reopening the table in its default order. A case
that derived its expectations from the owner would stay green through either,
which is the one thing it must not do.
"""

from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import skill_matrix_columns

# The eight columns in the order an operator reads them across, each with the
# heading it carries and whether it is right-aligned as a number.
_COLUMNS = (
    ("repo", "Repo", False),
    ("role", "Role", False),
    ("backend", "Backend", False),
    ("skill", "Skill", False),
    ("level", "Level", False),
    ("runs", "Runs", True),
    ("skill_runs", "Runs with skill", True),
    ("rate", "Trigger rate", True),
)

_NUMERIC_KEYS = frozenset(("runs", "skill_runs", "rate"))

_SORT_PARAM = "mtx_sort"

_DIR_PARAM = "mtx_dir"


class SkillMatrixColumnsTest(unittest.TestCase):
    """The column set every heading, link, and ordering is drawn from."""

    def test_the_eight_columns_are_in_order(self) -> None:
        self.assertEqual(
            tuple(
                (column.key, column.label, column.right_aligned)
                for column in skill_matrix_columns.SKILL_MATRIX_COLUMNS
            ),
            _COLUMNS,
        )

    def test_every_column_is_orderable_by_key(self) -> None:
        # A heading offering a sort the ordering cannot run is a click that
        # reopens the table in its default order.
        self.assertEqual(
            tuple(skill_matrix_columns.SKILL_MATRIX_SORT_KEYS),
            tuple(key for key, _label, _aligned in _COLUMNS),
        )

    def test_the_counts_are_the_numeric_columns(self) -> None:
        self.assertEqual(
            skill_matrix_columns.SKILL_MATRIX_NUMERIC_KEYS, _NUMERIC_KEYS,
        )


class SkillMatrixQueryParamsTest(unittest.TestCase):
    """The two spellings a saved sort travels in."""

    def test_the_sort_parameter_is_named(self) -> None:
        self.assertEqual(
            skill_matrix_columns.SKILL_MATRIX_SORT_PARAM, _SORT_PARAM,
        )

    def test_the_direction_parameter_is_named(self) -> None:
        self.assertEqual(
            skill_matrix_columns.SKILL_MATRIX_DIR_PARAM, _DIR_PARAM,
        )


if __name__ == "__main__":
    unittest.main()
