# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Credential-safe rendering of the libpq URL the replay dials.

`ANALYTICS_DB_URL` carries credentials in two distinct places -- the
`user:password@` netloc prefix and the `?user=&password=&sslpassword=&passfile=`
query string -- and the sync logs the endpoint it reached on both the connect
and the connection-established line. Both forms collapse to `***` before any of
that is printed, so a remote-Postgres password never lands in an operator's
stdout or in whatever log aggregator the host forwards to, while the scheme,
host, database, and every non-credential parameter survive verbatim so the
operator can still tell which endpoint answered.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# libpq treats parameter names as case-insensitive, so the comparison against
# this set is too: a `?PASSWORD=` spelling has to redact like `?password=`.
_REDACTED_QUERY_PARAMS = frozenset(("user", "password", "passfile", "sslpassword"))


def redacted_netloc(parts: Any) -> str:
    if not parts.username and not parts.password:
        return parts.netloc
    host = parts.hostname or ""
    netloc = f"{host}:{parts.port}" if parts.port else host
    return f"***@{netloc}" if netloc else "***"


def redacted_query(query: str) -> str:
    if not query:
        return query
    pairs = parse_qsl(query, keep_blank_values=True)
    redacted_pairs = [
        (key, "***" if key.lower() in _REDACTED_QUERY_PARAMS else param_value) for key, param_value in pairs
    ]
    if redacted_pairs == pairs:
        return query
    return urlencode(redacted_pairs, safe="*")


def redact_db_url(url: str) -> str:
    """Strip credentials from a libpq URL before it lands in a log line."""
    if not url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<db-url-unparseable>"
    return urlunsplit(
        (
            parts.scheme,
            redacted_netloc(parts),
            parts.path,
            redacted_query(parts.query),
            parts.fragment,
        )
    )
