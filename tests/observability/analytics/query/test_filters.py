# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one filter set becomes per table, and who it leaves with no rows."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from orchestrator.observability.analytics.query.conditions import (
    agent_event_excluded,
    append_where_condition,
    prepend_where_condition,
)
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.predicates import (
    build_rollup_window_where,
    build_view_window_where,
    build_window_where,
)

_AGENT_EXIT = "agent_exit"

_STAGE_ENTER = "stage_enter"

_STAGE_IMPLEMENTING = "implementing"

_REPO = "owner/r"

_ISSUE = 42

_YEAR = 2026

_WINDOW_END_DAY = 28

_WINDOW_START = datetime(_YEAR, 5, 1, tzinfo=timezone.utc)

_WINDOW_END = datetime(_YEAR, 5, _WINDOW_END_DAY, tzinfo=timezone.utc)

# The clause a cleared multiselect collapses to, and the required conditions
# the splices are checked with.
_CLEARED = " WHERE FALSE"

_REPO_CONDITION = " WHERE repo = %s"

_EVENT_CONDITION = "event = %s"

_FULL_FILTERS = WindowFilters(
    start=_WINDOW_START,
    end=_WINDOW_END,
    repo=_REPO,
    events=(_AGENT_EXIT, _STAGE_ENTER),
    stages=(_STAGE_IMPLEMENTING,),
    issue=_ISSUE,
)


class WindowClauseTest(unittest.TestCase):
    """The `ts`-scoped clause a base-table read concatenates into its SQL."""

    def test_an_unset_filter_set_adds_nothing(self) -> None:
        self.assertEqual(build_window_where(WindowFilters()), ("", []))

    def test_the_clause_and_bindings_share_one_order(self) -> None:
        # The markers are positional, so a reader that splices its own
        # condition onto either end binds its operand against this order.
        where, bindings = build_window_where(_FULL_FILTERS)
        self.assertEqual(
            where,
            " WHERE ts >= %s AND ts < %s AND repo = %s AND issue = %s"
            " AND event IN (%s, %s) AND stage IN (%s)",
        )
        self.assertEqual(bindings, [
            _WINDOW_START,
            _WINDOW_END,
            _REPO,
            _ISSUE,
            _AGENT_EXIT,
            _STAGE_ENTER,
            _STAGE_IMPLEMENTING,
        ])

    def test_an_issue_is_bound_as_a_number(self) -> None:
        # The drill-down carries whatever the widget handed it; `issue` is an
        # integer column, so a string would cost the index scan.
        _where, bindings = build_window_where(WindowFilters(issue=str(_ISSUE)))
        self.assertEqual(bindings, [_ISSUE])

    def test_a_cleared_selection_matches_no_rows(self) -> None:
        # The dashboard's cleared multiselect means "show nothing for this
        # dimension", which only holds if it reaches the SQL as a predicate.
        for dimension in ("events", "stages"):
            with self.subTest(dimension=dimension):
                where, bindings = build_window_where(
                    WindowFilters(**{dimension: ()}),
                )
                self.assertEqual(where, _CLEARED)
                self.assertEqual(bindings, [])


class RollupClauseTest(unittest.TestCase):
    """The same selection asked of the rollup, which is keyed by day."""

    def test_the_window_binds_dates_by_day(self) -> None:
        where, bindings = build_rollup_window_where(
            WindowFilters(start=_WINDOW_START, end=_WINDOW_END),
        )
        self.assertEqual(where, " WHERE day >= %s AND day < %s")
        self.assertEqual(bindings, [_WINDOW_START.date(), _WINDOW_END.date()])

    def test_a_cleared_selection_matches_nothing(self) -> None:
        where, _bindings = build_rollup_window_where(WindowFilters(events=()))
        self.assertEqual(where, _CLEARED)


class ViewClauseTest(unittest.TestCase):
    """`analytics_agent_runs` carries no `event` column to filter on."""

    def test_the_event_selection_alone_is_dropped(self) -> None:
        where, bindings = build_view_window_where(_FULL_FILTERS)
        self.assertEqual(
            where,
            " WHERE ts >= %s AND ts < %s AND repo = %s AND issue = %s"
            " AND stage IN (%s)",
        )
        self.assertEqual(bindings, [
            _WINDOW_START,
            _WINDOW_END,
            _REPO,
            _ISSUE,
            _STAGE_IMPLEMENTING,
        ])


class RequiredConditionTest(unittest.TestCase):
    """Which side a table's own condition lands on, and what it binds after."""

    def test_a_splice_keeps_the_generated_clause(self) -> None:
        self.assertEqual(
            append_where_condition(_REPO_CONDITION, "stage IS NOT NULL"),
            " WHERE repo = %s AND stage IS NOT NULL",
        )
        self.assertEqual(
            prepend_where_condition(_REPO_CONDITION, _EVENT_CONDITION),
            " WHERE event = %s AND repo = %s",
        )

    def test_an_empty_clause_becomes_the_condition(self) -> None:
        for splice in (append_where_condition, prepend_where_condition):
            with self.subTest(splice=splice.__name__):
                self.assertEqual(
                    splice("", _EVENT_CONDITION),
                    f" WHERE {_EVENT_CONDITION}",
                )


class AgentEventExclusionTest(unittest.TestCase):
    """Whether an event selection leaves a view-backed read anything to read."""

    def test_a_selection_without_agent_exit_excludes(self) -> None:
        selections = (
            (None, False),
            ((), True),
            ((_STAGE_ENTER,), True),
            ((_AGENT_EXIT, _STAGE_ENTER), False),
        )
        for events, excluded in selections:
            with self.subTest(events=events):
                self.assertIs(agent_event_excluded(events), excluded)


class FilterScopeTest(unittest.TestCase):
    """The three projections a reader narrows a filter set with."""

    def test_a_projection_drops_what_it_cannot_carry(self) -> None:
        scopes = (
            (
                _FULL_FILTERS.without_events(),
                WindowFilters(
                    start=_WINDOW_START,
                    end=_WINDOW_END,
                    repo=_REPO,
                    stages=(_STAGE_IMPLEMENTING,),
                    issue=_ISSUE,
                ),
            ),
            (
                _FULL_FILTERS.catalog_scope(),
                WindowFilters(
                    start=_WINDOW_START,
                    end=_WINDOW_END,
                    repo=_REPO,
                ),
            ),
            (
                _FULL_FILTERS.historical_scope(),
                WindowFilters(end=_WINDOW_END, repo=_REPO, issue=_ISSUE),
            ),
        )
        for scoped, expected in scopes:
            with self.subTest(scoped=scoped):
                self.assertEqual(scoped, expected)


if __name__ == "__main__":
    unittest.main()
