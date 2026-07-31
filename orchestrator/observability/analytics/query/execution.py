# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Running one read-only SELECT, and deciding whose connection it runs on.

`ReadQuery` is the resolved connection input one public read operation carries:
the caller's `db_url=` or the configured knob behind it, the caller's
`connect=` factory or the default, and the caller's `conn=` when it owns one
already. `available` is what a reader short-circuits on, so a read with neither
a supplied connection nor a configured URL returns an empty model instead of
dialing nowhere.

`select_rows` is the two connection paths that answer for. A caller-owned
`conn=` -- typically an `analytics_connection` scope running many reads on one
socket -- is used as-is and never closed, because its lifetime belongs to that
scope and not to this query. Without one, a fresh connection is opened and
closed in a `finally`, so a query that raises mid-stream cannot leak the
descriptor. Read-only either way: no commit, no rollback.

Every driver-level failure -- the connect, the cursor, the execute, or the
fetch -- comes back as `AnalyticsReadError`, so a caller has one type to catch
regardless of which step broke.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from orchestrator.observability.analytics.config import resolve_db_url
from orchestrator.observability.analytics.query.connections import (
    AnalyticsReadError,
    close_quietly,
    default_connect,
)


@dataclass(frozen=True)
class ReadQuery:
    """Resolved connection inputs shared by one public read operation."""

    db_url: Optional[str]
    connect_fn: Callable[[str], Any]
    conn: Any

    @classmethod
    def resolve(
        cls,
        db_url: Optional[str],
        connect: Optional[Callable[[str], Any]],
        conn: Any,
    ) -> ReadQuery:
        return cls(
            db_url=resolve_db_url(db_url),
            connect_fn=connect or default_connect,
            conn=conn,
        )

    @property
    def available(self) -> bool:
        """Whether a supplied connection or configured URL can serve reads."""
        return self.conn is not None or bool(self.db_url)

    def select(
        self,
        sql: str,
        bindings: Sequence[Any] = (),
    ) -> list[tuple]:
        """Execute one SELECT through the resolved connection path."""
        return select_rows(
            self.connect_fn,
            self.db_url,
            sql,
            bindings,
            conn=self.conn,
        )


def execute_select(
    conn: Any,
    sql: str,
    bindings: Sequence[Any],
) -> list[tuple]:
    """Run one SELECT on `conn` and return every row as a tuple.

    Neither opens nor closes `conn` -- the caller owns its lifetime.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(bindings))
            rows = cur.fetchall()
    except Exception as error:
        raise AnalyticsReadError(f"analytics query failed: {error}") from error
    return list(rows or [])


def connect_for_read(
    connect_fn: Callable[[str], Any],
    db_url: Optional[str],
) -> Any:
    """Open a fresh read connection, normalizing failures.

    An `AnalyticsReadError` the factory already raised (the default psycopg
    factory wraps its own connect failure) passes through unchanged rather than
    being double-wrapped; any other exception is wrapped so the caller sees a
    single type regardless of which driver raised it.
    """
    try:
        return connect_fn(db_url)
    except AnalyticsReadError:
        raise
    except Exception as error:
        raise AnalyticsReadError(f"could not connect to analytics database: {error}") from error


@contextlib.contextmanager
def read_connection(connect_fn: Callable[[str], Any], db_url: Optional[str]):
    """Open a fresh read connection and close it (best-effort) on exit, so a
    query that raises mid-stream never leaks the descriptor."""
    opened = connect_for_read(connect_fn, db_url)
    try:
        yield opened
    finally:
        close_quietly(opened)


def select_rows(
    connect_fn: Callable[[str], Any],
    db_url: Optional[str],
    sql: str,
    bindings: Sequence[Any] = (),
    *,
    conn: Any = None,
) -> list[tuple]:
    """Run a single SELECT and return all rows as tuples.

    Reuses `conn` when the caller supplied one and opens a fresh connection
    otherwise; see the module docstring for which lifetime each path owns.
    """
    if conn is not None:
        return execute_select(conn, sql, bindings)
    with read_connection(connect_fn, db_url) as opened:
        return execute_select(opened, sql, bindings)
