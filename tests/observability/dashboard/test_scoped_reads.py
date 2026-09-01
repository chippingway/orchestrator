# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The connection a page's read runs on, and how it reaches that read.

Every case here replaces the connection owner's scope, because what this owner
decides is only that a read is issued inside one and handed what it yielded --
what that scope opens, caches, and evicts is settled a package away.
"""

from __future__ import annotations

import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from typing import Any
from unittest.mock import patch

from orchestrator.observability.analytics.query import connection_cache
from orchestrator.observability.dashboard import scoped_reads

_CONNECTION = "socket"

_ENTERED = "entered"

_READ = "read"

_EXITED = "exited"

# What one read looks like from outside: opened, issued, closed, in that order.
_ONE_SCOPED_READ = (_ENTERED, _READ, _EXITED)

_ROWS = ("row",)

_REPO = "owner/repo"

_ISSUE = 42

_SCOPE_ATTRIBUTE = "analytics_connection"


@contextmanager
def _recording_scope(conn: Any, events: list[str]) -> Iterator[Any]:
    """A stand-in scope that reports when it is entered and left."""
    events.append(_ENTERED)
    try:
        yield conn
    finally:
        events.append(_EXITED)


def _record_read(
    calls: list[dict[str, Any]],
    **read_filters: Any,
) -> tuple[str, ...]:
    calls.append(read_filters)
    return _ROWS


def _record_scoped_read(events: list[str], **read_filters: Any) -> None:
    events.append(_READ)


class ScopedReadTest(unittest.TestCase):
    """One read, one checkout of this thread's analytics connection."""

    def test_the_read_is_handed_the_scoped_connection(self) -> None:
        # The connection reaches the read as a keyword and the filters travel
        # beside it untouched: a cached wrapper hashes only what it was
        # narrowed by, so the socket has to be added here rather than carried
        # in by the caller.
        calls: list[dict[str, Any]] = []

        read_rows = self._scoped_read(
            _CONNECTION,
            partial(_record_read, calls),
            repo=_REPO,
            issue=_ISSUE,
        )

        self.assertEqual(read_rows, _ROWS)
        self.assertEqual(
            calls,
            [{"conn": _CONNECTION, "repo": _REPO, "issue": _ISSUE}],
        )

    def test_each_read_runs_inside_its_own_scope(self) -> None:
        # The scope is what the connection owner evicts a broken socket on, so
        # a read that returned outside it would leave the next caller on this
        # thread holding a descriptor nobody checked.
        events: list[str] = []
        read = partial(_record_scoped_read, events)

        with patch.object(
            connection_cache,
            _SCOPE_ATTRIBUTE,
            partial(_recording_scope, _CONNECTION, events),
        ):
            scoped_reads.scoped_read(read)
            scoped_reads.scoped_read(read)

        self.assertEqual(tuple(events), _ONE_SCOPED_READ + _ONE_SCOPED_READ)

    def test_no_database_still_reaches_the_read(self) -> None:
        # The scope yields `None` when no database is configured, and every
        # read short-circuits on it into an empty result. Skipping the call
        # here instead would hand the page nothing to render its "no data"
        # state from.
        calls: list[dict[str, Any]] = []

        self._scoped_read(None, partial(_record_read, calls))

        self.assertEqual(calls, [{"conn": None}])

    def _scoped_read(self, conn: Any, getter: Any, **read_filters: Any) -> Any:
        """Run `getter` against a scope yielding `conn`."""
        with patch.object(
            connection_cache,
            _SCOPE_ATTRIBUTE,
            partial(_recording_scope, conn, []),
        ):
            return scoped_reads.scoped_read(getter, **read_filters)


if __name__ == "__main__":
    unittest.main()
