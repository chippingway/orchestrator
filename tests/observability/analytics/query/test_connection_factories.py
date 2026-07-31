# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a read dials with, and what it costs when the driver is missing."""
from __future__ import annotations

import logging
import unittest
from functools import partial

from orchestrator.observability.analytics.query.connections import (
    AnalyticsReadError,
    close_quietly,
    default_connect,
    default_persistent_connect,
    is_broken_connection_exc,
)
from tests.observability.analytics.query.query_fake_driver import (
    FakeConnect,
    FakeConnection,
    InterfaceError,
    OperationalError,
    patched_driver,
)
from tests.observability.analytics.query.query_test_support import (
    DB_URL,
    read_error_from,
)
from tests.observability.observability_test_support import _run_import_probe

# The whole point of deferring the import: a caller that only consumes the read
# dataclasses -- typing, tests, a docs build -- must not pay for the driver, or
# meet an ImportError from an install that never asked for one.
_DEFERRED_IMPORT_PROBE = """
import sys

import orchestrator.observability.analytics.query.connections

if "psycopg" in sys.modules:
    sys.exit("importing the owner loaded the driver")
"""

_FACTORIES = (default_connect, default_persistent_connect)

# The name a close failure has always been logged under, spelled out here so a
# module path that changes under an operator cannot take their filter with it.
_CLOSE_FAILURE_LOGGER = "orchestrator.analytics.connection"


class DeferredDriverTest(unittest.TestCase):
    """The psycopg import happens inside the call, and an absent driver comes
    back as the same exception every other read failure does.
    """

    def test_the_owner_imports_without_the_driver(self) -> None:
        completed = _run_import_probe(_DEFERRED_IMPORT_PROBE)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)

    def test_an_absent_driver_is_a_read_error(self) -> None:
        for factory in _FACTORIES:
            with self.subTest(factory=factory.__name__), patched_driver():
                error = read_error_from(partial(factory, DB_URL))
                self.assertIsInstance(error.__cause__, ImportError)


class ConnectFactoryTest(unittest.TestCase):
    """The two factories differ only in whether the socket they open is meant
    to outlive the query, and both normalize a refused dial.
    """

    def test_the_persistent_factory_autocommits(self) -> None:
        # A socket a thread keeps would otherwise sit idle in transaction after
        # every SELECT, and stay aborted after a failed one.
        driver = FakeConnect(FakeConnection())
        with patched_driver(driver):
            self.assertIsNotNone(default_persistent_connect(DB_URL))
        self.assertEqual(driver.calls, [(DB_URL, {"autocommit": True})])

    def test_the_per_query_factory_takes_the_default(self) -> None:
        driver = FakeConnect(FakeConnection())
        with patched_driver(driver):
            self.assertIsNotNone(default_connect(DB_URL))
        self.assertEqual(driver.calls, [(DB_URL, {})])

    def test_a_refused_dial_wraps_with_its_cause(self) -> None:
        refusal = RuntimeError("network unreachable")
        for factory in _FACTORIES:
            with self.subTest(factory=factory.__name__):
                with patched_driver(FakeConnect(refusal)):
                    error = read_error_from(partial(factory, DB_URL))
                self.assertIs(error.__cause__, refusal)


class BrokenConnectionTest(unittest.TestCase):
    """The detector the cache evicts on: it unwraps the read error every
    driver-level failure is wrapped in, and matches by class name so a fake can
    drive the eviction without psycopg installed.
    """

    def test_a_torn_down_socket_matches_by_name(self) -> None:
        for broken in (OperationalError, InterfaceError):
            with self.subTest(error=broken.__name__):
                self.assertTrue(is_broken_connection_exc(broken("dead")))

    def test_a_wrapped_socket_error_is_unwrapped(self) -> None:
        wrapper = AnalyticsReadError("wrap")
        wrapper.__cause__ = OperationalError("dead")
        self.assertTrue(is_broken_connection_exc(wrapper))

    def test_an_unrelated_error_is_not_broken(self) -> None:
        # A SQL syntax error or a programmer mistake leaves the socket usable,
        # so evicting on one would throw away a working connection per typo.
        self.assertFalse(is_broken_connection_exc(ValueError("not a socket")))
        self.assertFalse(is_broken_connection_exc(AnalyticsReadError("no cause")))


class CloseQuietlyTest(unittest.TestCase):
    """A close that fails after the rows came back is logged, not raised --
    under the name an operator's filter is already set on, which is why the
    logger is pinned rather than derived from where the owner now lives.
    """

    def test_a_failing_close_is_logged_and_swallowed(self) -> None:
        conn = FakeConnection()
        conn.raise_on_close = RuntimeError("close failed")
        with self.assertLogs(_CLOSE_FAILURE_LOGGER, level=logging.ERROR):
            close_quietly(conn)
        self.assertEqual(conn.close_called, 1)


if __name__ == "__main__":
    unittest.main()
