# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The connection scope one of a page's reads is issued inside.

Every read behind a page load enters the thread's analytics connection, and
this owner is the one place that entry is spelled. The reads are cached on
their filter key alone, so the connection cannot be an argument any of them
carries: a `psycopg.Connection` is unhashable, and a stringified one would make
every refreshed socket look like a cache miss. Checking it out here is what
keeps those keys connection-free while the reads still share one open socket.

The scope is per thread because a connection is not thread-safe, so a fan-out
worker running a reader opens its own on first use and reuses it for the rest
of that wave. What a scope exit keeps, what a broken socket evicts, and what an
unconfigured database yields are all the connection owner's decisions -- an
unconfigured one yields `None`, which is handed to the read unchanged because
every read short-circuits on it into an empty result rather than an error. What
is decided here is only that a read is issued inside a scope at all.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from orchestrator.observability.analytics.query import connection_cache


def scoped_read(getter: Callable[..., Any], /, **filters: Any) -> Any:
    """Run one read on this thread's analytics connection."""
    with connection_cache.analytics_connection() as conn:
        return getter(conn=conn, **filters)
