# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The stand-in driver, connection, and factory the query tests run on.

No test here dials a database. The connection owners are defined by what they
do with a `connect(db_url) -> conn` factory and the object it hands back, so a
factory that records its calls and a connection that records its cursors pin
every one of them -- and are the same injection shape every public read helper
accepts.

The two broken-socket stand-ins are named for the psycopg classes verbatim,
without a leading underscore: eviction matches a torn-down socket by class
`__name__` so the driver need not be installed, and a renamed stand-in would
silently stop driving the path it exists to drive.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any, Self
from unittest.mock import patch

_DRIVER = "psycopg"

# One recorded dial: the URL asked for and the keywords it was asked with.
_Dial = tuple[str | None, dict]

# Canned rows, and the same keyed by a fragment of the scan that asks for them.
_Rows = tuple[tuple, ...]
_RoutedRows = dict[str, _Rows]


class OperationalError(Exception):
    """Stand-in for `psycopg.OperationalError`, matched by class name."""


class InterfaceError(Exception):
    """Stand-in for `psycopg.InterfaceError`, matched the same way."""


class FakeCursor:
    """Records every (sql, bindings) executed and returns canned rows.

    A context manager, so the production `with conn.cursor() as cur:` block
    works unchanged. The rows are picked at `execute` time rather than at
    `fetchall`, so a read that runs two scans against one connection reads each
    one's answer back rather than the last one's.
    """

    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn
        self._rows: _Rows = ()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """No resources to release; the fake never suppresses."""

    def execute(self, sql: str, bindings: tuple) -> None:
        self._conn.executed.append((sql, tuple(bindings)))
        if self._conn.raise_on_execute is not None:
            raise self._conn.raise_on_execute
        self._rows = self._conn.rows_for_scan(sql)

    def fetchall(self) -> list[tuple]:
        return list(self._rows)


class FakeConnection:
    """One in-memory connection, counting what the owner did to it.

    A read that issues one scan is answered with `rows`. A read that issues
    several -- a catalog beside its runs, a window beside its history -- routes
    through `rows_for`, keyed by a fragment distinctive enough to name one
    scan, so a fixture says which answer belongs to which query instead of
    depending on the order they run in.
    """

    def __init__(
        self,
        rows: _Rows = (),
        rows_for: _RoutedRows | None = None,
    ) -> None:
        self.rows = rows
        self.rows_for = dict(rows_for or {})
        self.executed: list[tuple[str, tuple]] = []
        self.raise_on_execute: Exception | None = None
        self.raise_on_close: Exception | None = None
        self.close_called = 0

    def rows_for_scan(self, sql: str) -> _Rows:
        """Pick the canned rows for one scan, by the fragment naming it."""
        for fragment, rows in self.rows_for.items():
            if fragment in sql:
                return tuple(rows)
        return tuple(self.rows)

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        self.close_called += 1
        if self.raise_on_close is not None:
            raise self.raise_on_close

    def as_connect(self, _url: str | None) -> FakeConnection:
        """Serve as the owner's `connect(db_url) -> conn` factory."""
        return self


class FakeConnect:
    """One dial at a time, standing in for both factories a read can meet.

    Serves as the injected `connect(db_url) -> conn` an owner is handed and as
    the stand-in driver's own `connect`, so what a test asserts about a dial is
    the same either way. Hands back each connection in turn and records how it
    was called, which is how a test tells a reused socket from a reopened one
    without reaching into the cache. An exception among the connections is
    raised rather than returned, so a refused dial is one more entry. Running
    out is itself an assertion: a factory called more often than the test
    supplied for is a socket opened where one was meant to be reused, or where
    a caller-owned `conn=` was meant to make dialing unnecessary.
    """

    def __init__(self, *connections: Any) -> None:
        self._pending = list(connections)
        self.calls: list[_Dial] = []

    def __call__(self, url: str | None, **connect_kwargs: Any) -> Any:
        self.calls.append((url, connect_kwargs))
        if not self._pending:
            raise AssertionError(f"connect was called again for {url!r}")
        opened = self._pending.pop(0)
        if isinstance(opened, BaseException):
            raise opened
        return opened

    @property
    def urls(self) -> list[str | None]:
        """The URLs it was asked for, in order."""
        return [url for url, _ in self.calls]


@contextlib.contextmanager
def patched_driver(connect: Callable[..., Any] | None = None) -> Iterator[None]:
    """Answer the deferred `import psycopg` with a stand-in, or with nothing.

    An omitted `connect` installs no driver at all, which is the uninstalled
    case: a `None` in `sys.modules` is what makes `import psycopg` raise the
    way an absent package does.
    """
    driver = None if connect is None else SimpleNamespace(connect=connect)
    with patch.dict(sys.modules, {_DRIVER: driver}):
        yield
