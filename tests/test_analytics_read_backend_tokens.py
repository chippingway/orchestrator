# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics backend daily-token read tests."""

import unittest


from datetime import date


from tests.analytics_read_helpers import (
    _FakeConnection,
    _reload_read,
)


_STAGE_ENTER = "stage_enter"


_AGENT_RUNS_VIEW = "analytics_agent_runs"


_CLAUDE = "claude"


_CODEX = "codex"


_UNKNOWN = "unknown"


_YEAR = 2026


_DAY_ONE = date(_YEAR, 5, 1)


_DAY_TWO = date(_YEAR, 5, 2)


class BackendDailyTokensTest(unittest.TestCase):
    """`get_backend_daily_tokens` powers the redesigned dashboard's
    "By backend" hero toggle. It must read from the view, honor the
    agent-run event-filter short-circuit, and aggregate tokens across
    every agent run in the window (not a `LIMIT`-capped subset).
    """

    def test_unset_db_url_returns_empty(self) -> None:
        analytics_read = _reload_read(db_url="")
        self.assertEqual(
            analytics_read.get_backend_daily_tokens(
                connect=lambda url: _FakeConnection(),
            ),
            [],
        )

    def test_other_event_filter_skips_query(self) -> None:
        analytics_read = _reload_read()
        conn = _FakeConnection()
        rows = analytics_read.get_backend_daily_tokens(
            events=[_STAGE_ENTER],
            connect=conn.as_connect,
        )
        self.assertEqual(rows, [])
        self.assertEqual(conn.executed, [])

    def test_empty_events_short_circuits(self) -> None:
        analytics_read = _reload_read()
        conn = _FakeConnection()
        rows = analytics_read.get_backend_daily_tokens(
            events=[],
            connect=conn.as_connect,
        )
        self.assertEqual(rows, [])
        self.assertEqual(conn.executed, [])

    def test_reads_daily_backend_totals_from_view(self) -> None:
        analytics_read = _reload_read()
        conn = _FakeConnection()
        conn.rows_for = {
            _AGENT_RUNS_VIEW: [
                (_DAY_ONE, _CLAUDE, 12_000),
                (_DAY_ONE, _CODEX, 4_500),
                (_DAY_TWO, _CLAUDE, 8_000),
            ],
        }
        rows = analytics_read.get_backend_daily_tokens(connect=conn.as_connect)
        self.assertEqual(
            [(row.day, row.backend, row.total_tokens) for row in rows],
            [
                (_DAY_ONE, _CLAUDE, 12_000),
                (_DAY_ONE, _CODEX, 4_500),
                (_DAY_TWO, _CLAUDE, 8_000),
            ],
        )
        sql, _ = conn.first_query
        # Reads from the view -- so the agent-run filter contract
        # (no `event IN` clause) holds -- and groups by both day and
        # backend so the dashboard can build a per-day stack without
        # post-processing. Token total includes the cache band so the
        # backend stack matches the standalone mock's
        # `input + output + cache_read + cache_write` accounting.
        self.assertIn("FROM analytics_agent_runs", sql)
        self.assertNotIn("event IN", sql)
        self.assertIn("GROUP BY day, backend_label", sql)
        for token_column in (
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
        ):
            self.assertIn(token_column, sql)

    def test_null_backend_buckets_under_unknown(self) -> None:
        # `COALESCE(backend, 'unknown')` matches how
        # `get_backend_efficiency` surfaces NULL-backend rows.
        analytics_read = _reload_read()
        conn = _FakeConnection()
        conn.rows_for = {
            _AGENT_RUNS_VIEW: [
                (_DAY_ONE, _UNKNOWN, 1_000),
            ],
        }
        rows = analytics_read.get_backend_daily_tokens(connect=conn.as_connect)
        self.assertEqual([row.backend for row in rows], [_UNKNOWN])
