# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The socket one thread keeps, and the three things that take it away."""
from __future__ import annotations

import unittest
from functools import partial

from orchestrator.observability.analytics.query.connection_cache import (
    analytics_connection,
    close_thread_local_connection,
)
from orchestrator.observability.analytics.query.connections import AnalyticsReadError
from tests.observability.analytics.query.query_fake_driver import (
    FakeConnect,
    FakeConnection,
    OperationalError,
)
from tests.observability.analytics.query.query_test_support import (
    DB_URL,
    OTHER_DB_URL,
    configured_db_url,
    read_error_from,
)


def _opened_with(connect, **scope_fields):
    """Enter one scope and hand back the connection it yielded."""
    with analytics_connection(connect=connect, **scope_fields) as conn:
        return conn


class _ConnectionScopeCase(unittest.TestCase):
    """Drain the thread-local before and after each test.

    The cache is process-wide by design -- that is what makes a second `with`
    block cheap -- so nothing isolates one test from the next except draining
    it at both ends.
    """

    def setUp(self) -> None:
        close_thread_local_connection()
        self.addCleanup(close_thread_local_connection)


class ConnectionReuseTest(_ConnectionScopeCase):
    """The first scope on a thread opens the socket; every later one reuses it,
    and a normal exit leaves it open for them.
    """

    def test_a_disabled_url_yields_nothing(self) -> None:
        # Every public reader short-circuits on `conn=None`, so an operator
        # with no database still gets a "no data" page rather than a crash.
        with configured_db_url(None):
            self.assertIsNone(_opened_with(None))

    def test_a_second_scope_reuses_the_open_socket(self) -> None:
        cached = FakeConnection()
        # One connection to hand out: a second dial would fail the factory.
        connect = FakeConnect(cached)
        with configured_db_url():
            for _ in range(2):
                self.assertIs(_opened_with(connect), cached)
        self.assertEqual(connect.urls, [DB_URL])
        # Persistent: a normal exit must not close what the next scope reuses.
        self.assertEqual(cached.close_called, 0)

    def test_an_explicit_teardown_closes_it_once(self) -> None:
        cached = FakeConnection()
        with configured_db_url():
            self.assertIs(_opened_with(cached.as_connect), cached)
        close_thread_local_connection()
        close_thread_local_connection()
        self.assertEqual(cached.close_called, 1)

    def test_an_injected_factory_failure_wraps(self) -> None:
        refusal = RuntimeError("network unreachable")
        with configured_db_url():
            error = read_error_from(partial(_opened_with, FakeConnect(refusal)))
        self.assertIs(error.__cause__, refusal)

    def test_a_read_error_is_not_wrapped_twice(self) -> None:
        # The default factory wraps its own dial failure, so wrapping again
        # here would bury the driver exception one `__cause__` deeper than
        # every other read failure leaves it.
        refused = AnalyticsReadError("refused")
        with configured_db_url():
            error = read_error_from(partial(_opened_with, FakeConnect(refused)))
        self.assertIs(error, refused)


class ConnectionEvictionTest(_ConnectionScopeCase):
    """A cached socket survives exactly as long as it is still the right one:
    a torn-down socket and a changed URL each replace it.
    """

    def test_a_broken_socket_is_replaced(self) -> None:
        first = FakeConnection()
        second = FakeConnection()
        connect = FakeConnect(first, second)
        with configured_db_url():
            with self.assertRaises(OperationalError), analytics_connection(connect=connect):
                raise OperationalError("server closed the connection")
            self.assertEqual(first.close_called, 1)
            self.assertIs(_opened_with(connect), second)
        self.assertEqual(second.close_called, 0)

    def test_an_unrelated_error_keeps_the_socket(self) -> None:
        cached = FakeConnection()
        connect = FakeConnect(cached)
        with configured_db_url():
            with self.assertRaises(ValueError), analytics_connection(connect=connect):
                raise ValueError("not a broken socket")
            self.assertEqual(cached.close_called, 0)
            self.assertIs(_opened_with(connect), cached)

    def test_a_changed_url_closes_the_stale_socket(self) -> None:
        # Without this a thread that first read from one database would keep
        # answering from it after the caller switched, silently violating the
        # `db_url=` argument it was handed.
        first = FakeConnection()
        second = FakeConnection()
        connect = FakeConnect(first, second)
        self.assertIs(_opened_with(connect, db_url=DB_URL), first)
        self.assertIs(_opened_with(connect, db_url=OTHER_DB_URL), second)
        self.assertEqual(connect.urls, [DB_URL, OTHER_DB_URL])
        self.assertEqual((first.close_called, second.close_called), (1, 0))

    def test_the_same_url_does_not_reopen(self) -> None:
        # The URL-change eviction must not over-trigger: re-entering with the
        # same explicit URL is the reuse case the cache exists for.
        cached = FakeConnection()
        connect = FakeConnect(cached)
        for _ in range(2):
            self.assertIs(_opened_with(connect, db_url=DB_URL), cached)
        self.assertEqual(connect.urls, [DB_URL])


if __name__ == "__main__":
    unittest.main()
