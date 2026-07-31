# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Whose connection one SELECT runs on, and who closes it afterwards."""
from __future__ import annotations

import unittest
from functools import partial

from orchestrator.observability.analytics.query.connections import (
    AnalyticsReadError,
    default_connect,
)
from orchestrator.observability.analytics.query.execution import ReadQuery, select_rows
from tests.observability.analytics.query.query_fake_driver import (
    FakeConnect,
    FakeConnection,
)
from tests.observability.analytics.query.query_test_support import (
    DB_URL,
    OTHER_DB_URL,
    configured_db_url,
    read_error_from,
)

_SQL = "SELECT repo, COUNT(*) FROM analytics_events WHERE repo = %s"

_BINDINGS = ("owner/repo",)

_ROWS = (("owner/repo", 2),)

_QUERY_FAILURE = "syntax error at or near"


class ReadQueryResolutionTest(unittest.TestCase):
    """What one public read operation carries once its inputs are resolved."""

    def test_an_omitted_url_falls_back_to_the_setting(self) -> None:
        with configured_db_url():
            resolved = ReadQuery.resolve(None, None, None)
        self.assertEqual(resolved.db_url, DB_URL)
        self.assertIs(resolved.connect_fn, default_connect)

    def test_the_callers_inputs_win(self) -> None:
        conn = FakeConnection()
        connect = FakeConnect()
        with configured_db_url():
            resolved = ReadQuery.resolve(OTHER_DB_URL, connect, conn)
        self.assertEqual(resolved.db_url, OTHER_DB_URL)
        self.assertIs(resolved.connect_fn, connect)
        self.assertIs(resolved.conn, conn)

    def test_availability_needs_a_connection_or_url(self) -> None:
        # What every reader short-circuits on. A caller-owned connection is a
        # complete escape hatch, so it has to count even with the knob off.
        with configured_db_url(None):
            self.assertFalse(ReadQuery.resolve(None, None, None).available)
            self.assertTrue(
                ReadQuery.resolve(None, None, FakeConnection()).available,
            )
        with configured_db_url():
            self.assertTrue(ReadQuery.resolve(None, None, None).available)

    def test_a_select_runs_the_resolved_path(self) -> None:
        conn = FakeConnection(_ROWS)
        with configured_db_url(None):
            resolved = ReadQuery.resolve(None, FakeConnect(), conn)
        self.assertEqual(resolved.select(_SQL, _BINDINGS), list(_ROWS))
        self.assertEqual(conn.executed, [(_SQL, _BINDINGS)])


class CallerOwnedConnectionTest(unittest.TestCase):
    """A supplied `conn=` is used as-is: no dial, and no close.

    Its lifetime belongs to the scope that opened it -- typically an
    `analytics_connection` block running many reads on one socket -- so closing
    it here would tear down the next reader's connection.
    """

    def test_a_supplied_connection_is_left_open(self) -> None:
        conn = FakeConnection(_ROWS)
        rows = select_rows(FakeConnect(), DB_URL, _SQL, _BINDINGS, conn=conn)
        self.assertEqual(rows, list(_ROWS))
        self.assertEqual(conn.close_called, 0)

    def test_a_failed_query_wraps_without_closing(self) -> None:
        conn = FakeConnection()
        conn.raise_on_execute = RuntimeError(_QUERY_FAILURE)
        error = read_error_from(
            partial(select_rows, FakeConnect(), DB_URL, _SQL, conn=conn),
        )
        self.assertIs(error.__cause__, conn.raise_on_execute)
        self.assertEqual(conn.close_called, 0)


class OpenedConnectionTest(unittest.TestCase):
    """Without a `conn=`, the query owns the descriptor it opened."""

    def test_an_opened_connection_is_closed(self) -> None:
        conn = FakeConnection(_ROWS)
        rows = select_rows(conn.as_connect, DB_URL, _SQL, _BINDINGS)
        self.assertEqual(rows, list(_ROWS))
        self.assertEqual(conn.close_called, 1)

    def test_a_failed_query_still_closes_it(self) -> None:
        # The `finally` is the whole point: a query that raises mid-stream
        # would otherwise leak the descriptor on every dashboard load.
        conn = FakeConnection()
        conn.raise_on_execute = RuntimeError(_QUERY_FAILURE)
        read_error_from(partial(select_rows, conn.as_connect, DB_URL, _SQL))
        self.assertEqual(conn.close_called, 1)

    def test_a_failed_close_keeps_the_rows(self) -> None:
        conn = FakeConnection(_ROWS)
        conn.raise_on_close = RuntimeError("close failed")
        rows = select_rows(conn.as_connect, DB_URL, _SQL)
        self.assertEqual(rows, list(_ROWS))

    def test_a_refused_dial_wraps_with_its_cause(self) -> None:
        refusal = RuntimeError("network unreachable")
        error = read_error_from(
            partial(select_rows, FakeConnect(refusal), DB_URL, _SQL),
        )
        self.assertIs(error.__cause__, refusal)

    def test_a_read_error_is_not_wrapped_twice(self) -> None:
        refused = AnalyticsReadError("refused")
        error = read_error_from(
            partial(select_rows, FakeConnect(refused), DB_URL, _SQL),
        )
        self.assertIs(error, refused)


if __name__ == "__main__":
    unittest.main()
