# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one analytics connection a thread keeps, and when it is thrown away.

`analytics_connection` is the scope a page's reads run inside. The first entry
on a thread pays the ~1 s psycopg handshake; every later entry reuses the open
socket, which is the whole reason the cache exists. The connection therefore
survives a normal scope exit -- `close_thread_local_connection` is what drains
it, at shutdown or between tests.

One thread, one connection: a `psycopg.Connection` is not thread-safe, so the
entry is thread-local and a fan-out worker opens its own. Two things evict it.
A `with` block asking for a different `db_url=` than the cached socket was
opened against closes that socket first, because a thread that first read from
DB A must not keep answering from A after the caller switched to B. And an
error that escapes the scope looking like a torn-down socket
(`OperationalError` / `InterfaceError`, wrapped or raw) closes-and-discards the
entry before re-raising, so the next caller on the thread opens a fresh one
rather than inheriting a dead descriptor.

A disabled `ANALYTICS_DB_URL` yields `None`: every public read helper
short-circuits on `conn=None`, so an operator with no database configured still
gets a "no data" page rather than a crash.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from orchestrator.observability.analytics.config import resolve_db_url
from orchestrator.observability.analytics.query.connections import (
    AnalyticsReadError,
    close_quietly,
    default_persistent_connect,
    is_broken_connection_exc,
)

thread_local = threading.local()


def cached_entry(url: str) -> tuple[str, Any] | None:
    """Return this thread's matching cache entry, closing a stale one."""
    entry = getattr(thread_local, "entry", None)
    if entry is None:
        return None
    cached_url, cached_conn = entry
    if cached_url == url:
        return entry
    thread_local.entry = None
    close_quietly(cached_conn)
    return None


def open_cached_connection(
    url: str,
    connect_fn: Callable[[str], Any],
) -> Any:
    """Open and cache one persistent connection with normalized errors."""
    try:
        conn = connect_fn(url)
    except AnalyticsReadError:
        raise
    except Exception as error:
        raise AnalyticsReadError(
            f"could not connect to analytics database: {error}",
        ) from error
    thread_local.entry = (url, conn)
    return conn


def connection_for_url(
    url: str,
    connect_fn: Callable[[str], Any],
) -> Any:
    entry = cached_entry(url)
    if entry is None:
        return open_cached_connection(url, connect_fn)
    return entry[1]


def discard_broken_connection(exc: BaseException) -> None:
    """Evict this thread's cached socket when the escaped error broke it."""
    if not is_broken_connection_exc(exc):
        return
    entry = getattr(thread_local, "entry", None)
    if entry is None:
        return
    thread_local.entry = None
    close_quietly(entry[1])


@contextmanager
def analytics_connection(
    *,
    db_url: str | None = None,
    connect: Callable[[str], Any] | None = None,
) -> Iterator[Any]:
    """Yield this thread's persistent analytics connection.

    Yields ``None`` when the resolved URL is empty. Otherwise the cached
    connection is reused, opened on first use through `connect` or
    `default_persistent_connect`, keyed on the resolved URL, and evicted when a
    broken-socket error escapes the block -- see the module docstring for why
    each of those is the contract rather than an optimization.

    Tests inject a fake `connect(db_url) -> conn` factory the same shape as
    every public helper accepts.
    """
    url = resolve_db_url(db_url)
    if not url:
        yield None
        return
    conn = connection_for_url(url, connect or default_persistent_connect)
    try:
        yield conn
    except BaseException as exc:
        discard_broken_connection(exc)
        raise


def close_thread_local_connection() -> None:
    """Tear down any thread-local analytics connection on this thread.

    No-op when no connection is open. Intended for shutdown hooks and test
    teardown so a stale connection from one test does not bleed into the next.
    """
    entry = getattr(thread_local, "entry", None)
    if entry is None:
        return
    thread_local.entry = None
    close_quietly(entry[1])
