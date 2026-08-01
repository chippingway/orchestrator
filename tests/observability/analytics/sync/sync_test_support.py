# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a sync test writes on disk, and how it drives one replay over it.

Every module here needs the same two things and neither owner provides them: a
JSONL file that exists for the length of one test, written the way the sink
writes one, and a call that hands the run a source, a destination, and a
connection at once so nothing falls back to the configured knobs. Tests that
read the operator's side of a run take the same call with the log capture
around it, keyed on the literal logger name every sync surface writes under.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from orchestrator.observability.analytics.sync import run
from orchestrator.observability.analytics.sync.models import SyncResult
from tests.observability.analytics.sync.sync_fake_driver import FakeConnection, keep_payload

# A stand-in DSN: only its identity matters, since nothing here ever dials.
DB_URL = "postgresql://h/db"

# The stream an operator filters on, so a capture has to name it rather than a
# module the run happens to be entered through.
SYNC_LOGGER = "orchestrator.analytics.sync"

SAMPLE_TS = "2026-05-25T12:00:00+00:00"

STAGE_ENTER = "stage_enter"

AGENT_EXIT = "agent_exit"

ENCODING = "utf-8"

_LOG_FILENAME = "a.jsonl"

_LOG_LEVEL_INFO = "INFO"


@contextmanager
def raw_jsonl_log(lines: list[str]) -> Iterator[Path]:
    """Yield a temporary log file holding `lines` verbatim, garbage included."""
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / _LOG_FILENAME
        path.write_text("".join(f"{line}\n" for line in lines), encoding=ENCODING)
        yield path


@contextmanager
def jsonl_log(records: list[dict]) -> Iterator[Path]:
    """Yield a temporary log file written with the sink's own encoding."""
    with raw_jsonl_log([json.dumps(record, sort_keys=True) for record in records]) as path:
        yield path


def sample_record(
    *,
    issue: int = 1,
    event: str = STAGE_ENTER,
    ts: str = SAMPLE_TS,
    **extras,
) -> dict:
    """Build the minimal persisted analytics event envelope."""
    record = {
        "ts": ts,
        "repo": "owner/repo",
        "issue": issue,
        "event": event,
    }
    record.update(extras)
    return record


def sample_records(count: int) -> list[dict]:
    """Build `count` events whose one-based issue numbers keep them distinct."""
    return [sample_record(issue=issue) for issue in range(1, count + 1)]


def record_line(**overrides) -> str:
    """Render one sample record as the line the sink would have written."""
    return json.dumps(sample_record(**overrides), sort_keys=True)


def run_sync(
    log_path: Path,
    connection: FakeConnection,
    *,
    db_url: str = DB_URL,
) -> SyncResult:
    """Replay `log_path` over the fake connection, past the configured knobs."""
    return run.sync_jsonl_to_postgres(
        log_path=log_path,
        db_url=db_url,
        connect=connection.as_connect,
        json_adapter=keep_payload,
    )


def sync_capturing_logs(
    test_case: unittest.TestCase,
    log_path: Path,
    connection: FakeConnection,
    *,
    db_url: str = DB_URL,
) -> tuple[SyncResult, list[str]]:
    """Return one replay's result and the operator lines it logged."""
    with test_case.assertLogs(SYNC_LOGGER, level=_LOG_LEVEL_INFO) as captured:
        sync_result = run_sync(log_path, connection, db_url=db_url)
        log_lines = list(captured.output)
    return sync_result, log_lines
