# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a read answers for a whole window rather than for its rows."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from orchestrator.observability.analytics.query.overview_models import (
    DataExtent,
    FilterOptions,
)
from orchestrator.observability.analytics.query.raw_reads import (
    get_data_extent,
    get_event_breakdown,
    get_filter_options,
)
from tests.observability.analytics.query.query_fake_driver import (
    FakeConnect,
    FakeConnection,
)
from tests.observability.analytics.query.query_test_support import configured_db_url

_AGENT_EXIT = "agent_exit"

_STAGE_ENTER = "stage_enter"

_REPO_A = "owner/a"

_REPO_B = "owner/b"

_DIM_REPO = "repo"

# The five dropdowns the union fills, and the counts the assertions below read
# against them.
_FILTER_COLUMN_COUNT = 5

_AGENT_EXIT_COUNT = 5

_STAGE_ENTER_COUNT = 3

_YEAR = 2026

_EXTENT_MAX_DAY = 27

_EXTENT_MAX_HOUR = 12

_EXTENT_MIN = datetime(_YEAR, 4, 1, tzinfo=timezone.utc)

_EXTENT_MAX = datetime(
    _YEAR, 5, _EXTENT_MAX_DAY, _EXTENT_MAX_HOUR, 0, tzinfo=timezone.utc,
)


class FilterOptionsTest(unittest.TestCase):
    """The distinct values each dropdown offers, read off one union."""

    def test_an_unconfigured_database_offers_nothing(self) -> None:
        with configured_db_url(None):
            options = get_filter_options(connect=FakeConnect())
        self.assertEqual(options, FilterOptions())

    def test_one_query_fills_every_dropdown(self) -> None:
        # Five `SELECT DISTINCT` round-trips collapsed into one union, so the
        # rows arrive tagged with the column they belong to and are bucketed
        # and sorted here. The fixture emits each pair out of order so the
        # ascending sort is the reason the assertions hold.
        conn = FakeConnection(rows=(
            (_DIM_REPO, _REPO_B), (_DIM_REPO, _REPO_A),
            ("event", _STAGE_ENTER), ("event", _AGENT_EXIT),
            ("stage", "validating"), ("stage", "implementing"),
            ("backend", "codex"), ("backend", "claude"),
            ("agent_role", "review"), ("agent_role", "dev"),
        ))
        with configured_db_url():
            options = get_filter_options(connect=conn.as_connect)
        self.assertEqual(
            options,
            FilterOptions(
                repos=(_REPO_A, _REPO_B),
                events=(_AGENT_EXIT, _STAGE_ENTER),
                stages=("implementing", "validating"),
                backends=("claude", "codex"),
                agent_roles=("dev", "review"),
            ),
        )
        self.assertEqual(len(conn.executed), 1)
        # Each leg keeps its own NULL exclusion, which is what preserves the
        # per-column partial scan the union is built from.
        scan_sql, _ = conn.executed[0]
        self.assertEqual(scan_sql.count("IS NOT NULL"), _FILTER_COLUMN_COUNT)
        self.assertEqual(conn.close_called, 1)

    def test_a_row_it_cannot_place_is_dropped(self) -> None:
        # Neither row reaches a bucket: the SQL already excludes NULLs, and a
        # dimension the reader has not learned about would otherwise land in a
        # bucket the result model has no field for.
        conn = FakeConnection(rows=(
            (_DIM_REPO, _REPO_A),
            (_DIM_REPO, None),
            ("model", "claude-4-7"),
            (_DIM_REPO, _REPO_B),
        ))
        with configured_db_url():
            options = get_filter_options(connect=conn.as_connect)
        self.assertEqual(options.repos, (_REPO_A, _REPO_B))

    def test_an_empty_table_still_answers(self) -> None:
        conn = FakeConnection()
        with configured_db_url():
            options = get_filter_options(connect=conn.as_connect)
        self.assertEqual(options, FilterOptions())
        self.assertEqual(len(conn.executed), 1)


class DataExtentTest(unittest.TestCase):
    """How far the recorded data reaches, so a date picker can land on it."""

    def test_an_unconfigured_database_reaches_nowhere(self) -> None:
        with configured_db_url(None):
            extent = get_data_extent(connect=FakeConnect())
        self.assertEqual(extent, DataExtent())

    def test_the_bounds_come_back_as_the_min_and_max(self) -> None:
        conn = FakeConnection(rows=((_EXTENT_MIN, _EXTENT_MAX),))
        with configured_db_url():
            extent = get_data_extent(connect=conn.as_connect)
        self.assertEqual(extent, DataExtent(min_ts=_EXTENT_MIN, max_ts=_EXTENT_MAX))
        scan_sql, _ = conn.executed[0]
        self.assertIn("MIN(ts)", scan_sql)
        self.assertIn("MAX(ts)", scan_sql)

    def test_an_empty_table_reaches_nowhere(self) -> None:
        # `MIN`/`MAX` over no rows is one row of two NULLs, which is the same
        # "nothing recorded yet" answer an unconfigured database gives.
        conn = FakeConnection(rows=((None, None),))
        with configured_db_url():
            extent = get_data_extent(connect=conn.as_connect)
        self.assertEqual(extent, DataExtent())


class EventBreakdownTest(unittest.TestCase):
    """How many of each event fired inside the window."""

    def test_an_unconfigured_database_counts_nothing(self) -> None:
        with configured_db_url(None):
            self.assertEqual(get_event_breakdown(connect=FakeConnect()), [])

    def test_counts_come_back_ranked(self) -> None:
        conn = FakeConnection(rows=(
            (_AGENT_EXIT, _AGENT_EXIT_COUNT),
            (_STAGE_ENTER, _STAGE_ENTER_COUNT),
        ))
        with configured_db_url():
            rows = get_event_breakdown(connect=conn.as_connect)
        self.assertEqual(
            [(row.event, row.count) for row in rows],
            [(_AGENT_EXIT, _AGENT_EXIT_COUNT), (_STAGE_ENTER, _STAGE_ENTER_COUNT)],
        )
        scan_sql, _ = conn.executed[0]
        self.assertIn("GROUP BY event", scan_sql)
        # Ties break on the event name, so redrawing the same window cannot
        # reshuffle the table.
        self.assertIn("ORDER BY c DESC, event ASC", scan_sql)


if __name__ == "__main__":
    unittest.main()
