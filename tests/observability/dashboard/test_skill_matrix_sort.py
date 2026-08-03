# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The order the matrix's rows are drawn in, and the click that chose it.

The cases name the two halves of that: what a page URL is read back as --
including the stale and half-written ones a shared link can arrive as -- and
what each order actually is. The default is pinned as the key it sorts on
rather than only through a rendered table, because it orders on two readings at
once and a table can agree with it for the wrong reason.

The URL is spelled out rather than read off the owner: a sort an operator
bookmarked or shared names these two parameters, so a rename has to fail here
rather than pass against whatever the owner now writes.
"""

from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import skill_matrix_sort
from tests.observability.dashboard.skill_matrix_test_support import (
    REPO_B,
    CellCase,
    cell,
    cells,
)

_SORT_PARAM = "mtx_sort"

_DIR_PARAM = "mtx_dir"

_SORT_KEY_RUNS = "runs"

_SORT_KEY_RATE = "rate"

_SORT_KEY_REPO = "repo"

_UNKNOWN_COLUMN = "bogus"

_ASCENDING = "asc"

_DESCENDING = "desc"

# A repository the sink capitalized differently from its siblings, so an
# ordering is read off a name an operator sees as one repository.
_SHOUTED_REPO = "A/REPO"

_DEFAULT_ORDER = (None, False)

# The rate the shared cell case carries: one of its four runs reached for the
# skill.
_CELL_RATE = 0.25


class ParseSkillMatrixSortTest(unittest.TestCase):
    """What one page URL is read back as."""

    def test_a_named_column_reads_its_direction(self) -> None:
        cases = (
            ({_SORT_PARAM: _SORT_KEY_RUNS}, (_SORT_KEY_RUNS, False)),
            (
                {_SORT_PARAM: _SORT_KEY_RUNS, _DIR_PARAM: _DESCENDING},
                (_SORT_KEY_RUNS, True),
            ),
            (
                {_SORT_PARAM: _SORT_KEY_RUNS, _DIR_PARAM: _ASCENDING},
                (_SORT_KEY_RUNS, False),
            ),
            (
                {_SORT_PARAM: _SORT_KEY_RATE, _DIR_PARAM: _DESCENDING},
                (_SORT_KEY_RATE, True),
            ),
        )
        for query_params, expected in cases:
            with self.subTest(params=query_params):
                self.assertEqual(
                    skill_matrix_sort.parse_skill_matrix_sort(query_params),
                    expected,
                )

    def test_an_unreadable_link_opens_default(self) -> None:
        # A link written against a column the vocabulary no longer offers, and
        # a direction with no column beside it, are both pages an operator
        # opened to read a table rather than a raise.
        for query_params in (
            {},
            {_SORT_PARAM: _UNKNOWN_COLUMN, _DIR_PARAM: _DESCENDING},
            {_DIR_PARAM: _DESCENDING},
        ):
            with self.subTest(params=query_params):
                self.assertEqual(
                    skill_matrix_sort.parse_skill_matrix_sort(query_params),
                    _DEFAULT_ORDER,
                )

    def test_the_parameters_are_passed_by_name(self) -> None:
        self.assertEqual(
            skill_matrix_sort.parse_skill_matrix_sort(
                params={_SORT_PARAM: _SORT_KEY_RUNS},
            ),
            (_SORT_KEY_RUNS, False),
        )


class SkillMatrixOrderTest(unittest.TestCase):
    """What each of the two orders is."""

    def test_a_column_nobody_offers_is_identity(self) -> None:
        rows = cells(CellCase(repo=REPO_B), CellCase())
        for sort_key in (None, _UNKNOWN_COLUMN):
            with self.subTest(sort_key=sort_key):
                self.assertEqual(
                    skill_matrix_sort.sort_skill_matrix_rows(
                        rows, sort_key, True,
                    ),
                    rows,
                )

    def test_a_name_orders_case_insensitively(self) -> None:
        shouted, plain = cells(
            CellCase(repo=_SHOUTED_REPO), CellCase(repo=REPO_B),
        )
        self.assertEqual(
            skill_matrix_sort.sort_skill_matrix_rows(
                [plain, shouted], _SORT_KEY_REPO, False,
            ),
            [shouted, plain],
        )

    def test_the_default_key_is_repo_up_rate_down(self) -> None:
        self.assertEqual(
            skill_matrix_sort.skill_matrix_default_sort_key(
                cell(CellCase(repo=_SHOUTED_REPO)),
            ),
            (_SHOUTED_REPO.lower(), -_CELL_RATE),
        )


if __name__ == "__main__":
    unittest.main()
