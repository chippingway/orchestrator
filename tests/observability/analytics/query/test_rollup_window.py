# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What all seven rollup reads answer the same way about a window.

The per-read modules beside this one cover each family's own columns; these are
the invariants that have to hold across every one of them, checked in one place
so a rewrite of a single read cannot quietly drop the scan target, the day
binding, or the cleared-multiselect contract the other six keep.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from orchestrator.observability.analytics.query.rollup_reads import (
    get_backend_efficiency,
    get_kpi_prev,
    get_repo_breakdown,
    get_stage_breakdown,
    get_summary,
    get_throughput_breakdown,
    get_time_series,
)
from tests.observability.analytics.analytics_assertions import assert_sql_fragments
from tests.observability.analytics.query.query_fake_driver import FakeConnection
from tests.observability.analytics.query.query_test_support import configured_db_url

_ROLLUP_SCAN = "FROM analytics_daily_rollup"

_EVENTS_SCAN = "FROM analytics_events"

_AGENT_RUNS_SCAN = "FROM analytics_agent_runs"

_FALSE_PREDICATE = "FALSE"

_REPO = "owner/r"

_ISSUE = 42

_YEAR = 2026

_WINDOW_END_DAY = 28

_WINDOW_START = datetime(_YEAR, 5, 1, tzinfo=timezone.utc)

_WINDOW_END = datetime(_YEAR, 5, _WINDOW_END_DAY, tzinfo=timezone.utc)

_ROLLUP_READS = (
    get_summary,
    get_kpi_prev,
    get_time_series,
    get_stage_breakdown,
    get_repo_breakdown,
    get_backend_efficiency,
    get_throughput_breakdown,
)

# The reads whose scan survives a cleared multiselect and has to carry the
# false predicate instead. The throughput read is absent from both groups
# because it answers without SQL either way, and the backend read is absent
# from the events group for the same reason: an events selection with no
# `agent_exit` in it short-circuits before a clause is built.
_CLEARED_EVENTS_READS = (
    get_summary,
    get_kpi_prev,
    get_time_series,
    get_stage_breakdown,
    get_repo_breakdown,
)

_CLEARED_STAGES_READS = (*_CLEARED_EVENTS_READS, get_backend_efficiency)


class RollupScanTargetTest(unittest.TestCase):
    """Every one of the seven reads the day-bucketed rollup, and only it."""

    def test_no_read_falls_back_to_a_row_level_scan(self) -> None:
        for read in _ROLLUP_READS:
            with self.subTest(read=read.__name__):
                conn = FakeConnection()
                with configured_db_url():
                    read(connect=conn.as_connect)
                self.assertEqual(len(conn.executed), 1)
                scan_sql, _ = conn.executed[0]
                self.assertIn(_ROLLUP_SCAN, scan_sql)
                self.assertNotIn(_EVENTS_SCAN, scan_sql)
                self.assertNotIn(_AGENT_RUNS_SCAN, scan_sql)


class RollupWindowBindingTest(unittest.TestCase):
    """The window and the issue filter narrow every read the same way."""

    def test_the_window_binds_as_days(self) -> None:
        # The rollup is keyed by a UTC date, so projecting the caller's
        # midnight-aligned bounds before binding keeps the plan a day-range
        # scan instead of a cast computed at execute time.
        for read in _ROLLUP_READS:
            with self.subTest(read=read.__name__):
                conn = FakeConnection()
                with configured_db_url():
                    read(start=_WINDOW_START, end=_WINDOW_END, connect=conn.as_connect)
                scan_sql, bindings = conn.executed[0]
                assert_sql_fragments(self, scan_sql, ("day >= %s", "day < %s"))
                self.assertIn(_WINDOW_START.date(), bindings)
                self.assertIn(_WINDOW_END.date(), bindings)

    def test_the_issue_filter_narrows_every_read(self) -> None:
        # The rollup key carries `issue`, so the drill-down a page offers on
        # one issue narrows the same seven reads the whole-window view uses.
        for read in _ROLLUP_READS:
            with self.subTest(read=read.__name__):
                conn = FakeConnection()
                with configured_db_url():
                    read(repo=_REPO, issue=_ISSUE, connect=conn.as_connect)
                scan_sql, bindings = conn.executed[0]
                self.assertIn("issue = %s", scan_sql)
                self.assertIn(_ISSUE, bindings)


class ClearedSelectionTest(unittest.TestCase):
    """A cleared multiselect means no row matches, not no filter."""

    def test_a_cleared_events_choice_matches_none(self) -> None:
        for read in _CLEARED_EVENTS_READS:
            with self.subTest(read=read.__name__):
                conn = FakeConnection()
                with configured_db_url():
                    read(events=[], connect=conn.as_connect)
                scan_sql, _ = conn.executed[0]
                self.assertIn(_FALSE_PREDICATE, scan_sql)

    def test_a_cleared_stages_choice_matches_none(self) -> None:
        for read in _CLEARED_STAGES_READS:
            with self.subTest(read=read.__name__):
                conn = FakeConnection()
                with configured_db_url():
                    read(stages=[], connect=conn.as_connect)
                scan_sql, _ = conn.executed[0]
                self.assertIn(_FALSE_PREDICATE, scan_sql)


if __name__ == "__main__":
    unittest.main()
