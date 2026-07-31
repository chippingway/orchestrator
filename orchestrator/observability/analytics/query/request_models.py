# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The typed parts one read call is normalized into.

A public read is called with one flat keyword list, and every family then asks
the same three questions of it: what the rows are filtered by, which connection
they are read over, and which reader-specific knob -- a row limit, an ordering,
an hour offset -- shapes this particular query. Each is its own value, so the
filter projection the SQL is built from cannot pick up a connection field, and
a knob only one family accepts stays out of the shape every family shares.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional, Sequence


@dataclass(frozen=True)
class ReadFilters:
    """Window and domain filters shared by analytics readers."""

    start: Optional[datetime] = None
    end: Optional[datetime] = None
    repo: Optional[str] = None
    events: Optional[Sequence[str]] = None
    stages: Optional[Sequence[str]] = None
    issue: Optional[int] = None


@dataclass(frozen=True)
class ReadConnection:
    """Connection selection for one analytics read."""

    db_url: Optional[str] = None
    connect: Optional[Callable[[str], Any]] = None
    conn: Any = None


@dataclass(frozen=True)
class ReadOptions:
    """Reader-specific limit, ordering, and timezone controls."""

    limit: Optional[int] = None
    sort_by: Optional[str] = None
    tz_offset_hours: int = 0


@dataclass(frozen=True)
class ReadRequest:
    """Normalized input consumed by analytics query implementations."""

    filters: ReadFilters
    connection: ReadConnection
    options: ReadOptions
