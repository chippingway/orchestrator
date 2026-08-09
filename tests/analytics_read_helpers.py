# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Shared fake psycopg connection / cursor and settings-reparse helpers
for the analytics read-model test suite.

The `test_analytics_read*.py` modules all re-parse `ANALYTICS_DB_URL`
against a hermetic env and drive the readers through an in-memory
`_FakeConnection` / `_FakeCursor` pair, so the fakes and the `_reload`
shim live here in one place.
"""
from __future__ import annotations

import importlib

from tests.analytics_reload_helpers import reload_analytics

# The stand-in Postgres DSN every read-model test wires into
# `ANALYTICS_DB_URL`; only its presence matters, the fake connection
# never dials it.
_POSTGRES_URL = "postgresql://h/db"
_DB_URL_ENV = "ANALYTICS_DB_URL"


def _reload(env: dict[str, str] | None = None):
    """Re-parse the analytics knobs against `env` and hand back the settings
    holder beside the `orchestrator.analytics.read` facade.

    A read resolves `ANALYTICS_DB_URL` off that holder inside the call, so
    landing the test's env on it is all the facade needs -- the facade itself
    forwards to owners that hold no settings of their own.
    """
    _, settings = reload_analytics(env)
    return settings, importlib.import_module("orchestrator.analytics.read")


def _reload_read(db_url: str = _POSTGRES_URL):
    """Point `ANALYTICS_DB_URL` at `db_url` and return the read facade.

    Most read-model tests never inspect the settings holder, so this folds the
    URL wiring behind a single default.
    """
    _, analytics_read = _reload({_DB_URL_ENV: db_url})
    return analytics_read


class _FakeCursor:
    """Records every (sql, params) executed and returns canned rows.

    Implemented as a context manager so the production
    `with conn.cursor() as cur:` block works unchanged. `rows_for`
    is a dict mapping a substring of the SQL to the rows the cursor
    should return -- tests register expected query shapes by their
    most distinctive keyword (`COUNT(*) AS total_events`,
    `date_trunc`, etc.) so a refactor of unrelated SQL doesn't
    accidentally trip the assertion.
    """

    def __init__(self, conn: "_FakeConnection") -> None:
        self._conn = conn
        self._next_rows: list[tuple] = []

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """No resources to release; the fake never suppresses."""

    def execute(self, sql: str, sql_params: tuple) -> None:
        self._conn.executed.append((sql, tuple(sql_params)))
        if self._conn.raise_on_execute is not None:
            raise self._conn.raise_on_execute
        self._next_rows = []
        for needle, rows in self._conn.rows_for.items():
            if needle in sql:
                self._next_rows = list(rows)
                break

    def fetchall(self) -> list[tuple]:
        return list(self._next_rows)


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self.rows_for: dict[str, list[tuple]] = {}
        self.raise_on_execute: Exception | None = None
        self.close_called = 0

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def close(self) -> None:
        self.close_called += 1

    def as_connect(self, _url: str) -> "_FakeConnection":
        """Serve as the reader's `connect(db_url) -> conn` callable,
        always yielding this same fake so a test can inspect the
        executed SQL after the reader returns.
        """
        return self

    @property
    def first_query(self) -> tuple[str, tuple]:
        """The single (sql, params) round-trip the reader issued."""
        return self.executed[0]
