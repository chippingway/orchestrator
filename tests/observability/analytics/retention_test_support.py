# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Sink fixtures and pinned ages shared by the retention tests.

Every prune test needs the same two things: a temporary JSONL file the
analytics knobs are re-parsed against, and a fixed "now" so a record's age is
a property of the fixture rather than of when the suite ran. Both sinks are
built the same way here so a test that pins one against the other -- the
independence pair especially -- cannot accidentally give them different
retention windows.
"""

from __future__ import annotations

import contextlib
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from tests.observability.analytics.analytics_reload_helpers import reload_analytics as _reload

ANALYTICS_LOG_PATH = "ANALYTICS_LOG_PATH"

ANALYTICS_RETENTION_DAYS = "ANALYTICS_RETENTION_DAYS"

TRAJECTORY_LOG_PATH = "TRAJECTORY_LOG_PATH"

TRAJECTORY_RETENTION_DAYS = "TRAJECTORY_RETENTION_DAYS"

DEFAULT_RETENTION_DAYS = 90

DEFAULT_RETENTION = str(DEFAULT_RETENTION_DAYS)

_PRUNE_NOW_DAY = 25

_PRUNE_NOW_HOUR = 12

_YEAR = 2026

# The pinned comparison point every prune in these tests is handed, so the
# ages below mean the same thing on any day the suite runs.
PRUNE_NOW = datetime(_YEAR, 5, _PRUNE_NOW_DAY, _PRUNE_NOW_HOUR, 0, 0, tzinfo=UTC)

FRESH_RECORD_AGE_DAYS = 1

RECENT_RECORD_AGE_DAYS = 10

OLD_RECORD_AGE_DAYS = 100

VERY_OLD_RECORD_AGE_DAYS = 200

ANCIENT_RECORD_AGE_DAYS = 1000

TIMESTAMP_KEY = "ts"

SESSION_ID_KEY = "session_id"

ISSUE_KEY = "issue"

EVENT_KEY = "event"

REPO_KEY = "repo"

REPO_SHORT = "o/r"

ENCODING = "utf-8"

@contextlib.contextmanager
def analytics_sink(retention: str | None = None) -> Iterator[Path]:
    """Point the analytics knobs at a temporary `analytics.jsonl`."""
    with tempfile.TemporaryDirectory() as sink_dir:
        path = Path(sink_dir) / "analytics.jsonl"
        environment = {ANALYTICS_LOG_PATH: str(path)}
        if retention is not None:
            environment[ANALYTICS_RETENTION_DAYS] = retention
        _reload(environment)
        yield path


@contextlib.contextmanager
def trajectory_sink(retention: str | None = None) -> Iterator[Path]:
    """Point the trajectory knobs at a temporary `trajectory.jsonl`."""
    with tempfile.TemporaryDirectory() as sink_dir:
        path = Path(sink_dir) / "trajectory.jsonl"
        environment = {TRAJECTORY_LOG_PATH: str(path)}
        if retention is not None:
            environment[TRAJECTORY_RETENTION_DAYS] = retention
        _reload(environment)
        yield path
