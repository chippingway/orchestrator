# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a run of the page narrows and displays its window by.

One owner for the four selections a page carries beside the window -- the
display offset a timestamp is rendered in, the issue number typed into a free
text box, the stage multiselect, and the key every cached read is stored
under -- because the key is built from the other three. A selection normalized
one way here and hashed another way there would let two different filter sets
share a cache entry, so the normalization and the key it feeds sit together.
The stage filter keeps three states apart: `None` is "no clause", `[]` is the
cleared multiselect that must show nothing, and a proper subset is the clause
itself.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

from orchestrator.observability.dashboard.windows import DateWindow

MIN_UTC_OFFSET = -12
MAX_UTC_OFFSET = 14
TZ_OFFSET_OPTIONS = tuple(range(MIN_UTC_OFFSET, MAX_UTC_OFFSET + 1))
DEFAULT_TZ_OFFSET_HOURS = 7


class DashboardCacheKey(NamedTuple):
    start: datetime
    end: datetime
    repo: str | None
    events: tuple[str, ...] | None
    stages: tuple[str, ...] | None
    issue: int | None


def format_tz_offset(hours: int) -> str:
    if hours == 0:
        return "UTC"
    sign = "+" if hours > 0 else "-"
    return f"UTC{sign}{abs(int(hours))}"


def shift_ts(timestamp: Any, offset: timedelta) -> Any:
    if timestamp is None:
        return None
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            return timestamp + offset
        return timestamp.astimezone(timezone(offset))
    return timestamp


def parse_issue_number(raw_issue: str) -> int | None:
    if not raw_issue:
        return None
    cleaned = raw_issue.strip().lstrip("#").strip()
    if not cleaned:
        return None
    try:
        issue_number = int(cleaned)
    except ValueError:
        return None
    return issue_number if issue_number > 0 else None


def resolve_stage_filter(
    selected: Sequence[str],
    available: Sequence[str],
) -> list[str] | None:
    if not available or set(selected) == set(available):
        return None
    return list(selected)


def cache_key(
    window: DateWindow,
    repo: str | None,
    events: Sequence[str] | None,
    stages: Sequence[str] | None,
    issue: int | None,
) -> DashboardCacheKey:
    event_names = None if events is None else tuple(events)
    stage_names = None if stages is None else tuple(stages)
    return DashboardCacheKey(
        start=window.start,
        end=window.end,
        repo=repo,
        events=event_names,
        stages=stage_names,
        issue=issue,
    )
