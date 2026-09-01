# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What an omitted input falls back to, and which states are a no-op."""
from __future__ import annotations

import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

from orchestrator.observability.analytics.sync import run
from orchestrator.observability.analytics.sync.models import SyncResult
from tests.observability.analytics.sync.sync_fake_driver import FakeConnection, keep_payload
from tests.observability.analytics.sync.sync_test_support import (
    DB_URL,
    jsonl_log,
    sample_record,
)

# The holder the knobs are bound on and where a caller patches one, which is
# what `config.live_settings` resolves a fallback through.
_SETTINGS_HOLDER = "orchestrator.observability.analytics.settings"

_LOG_PATH_SETTING = "ANALYTICS_LOG_PATH"

_DB_URL_SETTING = "ANALYTICS_DB_URL"

_ABSENT_FILENAME = "never-written.jsonl"

# Where the source path sits in the row: third from the end, ahead of the line
# number and the hash.
_SOURCE_PATH_CELL = -3


@contextmanager
def _configured_sink(
    log_path: Path | None,
    db_url: str | None,
) -> Iterator[None]:
    """Pin what the two omitted inputs resolve to for the body."""
    holder = import_module(_SETTINGS_HOLDER)
    with patch.object(holder, _LOG_PATH_SETTING, log_path):
        with patch.object(holder, _DB_URL_SETTING, db_url):
            yield


class _DialLog:
    """A connection factory that records the dial a no-op must never make."""

    def __init__(self) -> None:
        self.dialed: list[str] = []

    def connect(self, db_url: str) -> FakeConnection:
        self.dialed.append(db_url)
        return FakeConnection()


def _sync_without_dialing(test_case: unittest.TestCase) -> SyncResult:
    """Run the configured sync and assert it never reached for a connection."""
    dial_log = _DialLog()
    sync_result = run.sync_jsonl_to_postgres(connect=dial_log.connect)
    test_case.assertEqual(dial_log.dialed, [])
    return sync_result


class DisabledSyncTest(unittest.TestCase):
    """Three configured states are a silent no-op rather than a failure: no
    database, no sink, and a sink whose file has not been written yet. None of
    them opens a connection, and each returns empty counts, because the CLI is
    safe to schedule before the operator has deployed Postgres.
    """

    def test_no_op_when_the_database_url_is_unset(self) -> None:
        with jsonl_log([sample_record()]) as path:
            with _configured_sink(path, None):
                sync_result = _sync_without_dialing(self)
        self.assertEqual(sync_result.inserted, 0)
        self.assertEqual(sync_result.total_lines, 0)

    def test_no_op_when_the_sink_is_disabled(self) -> None:
        with _configured_sink(None, DB_URL):
            sync_result = _sync_without_dialing(self)
        self.assertEqual(sync_result.inserted, 0)

    def test_no_op_when_the_file_is_absent(self) -> None:
        # Configured, but nothing has emitted a record yet: do not dial, do not
        # fail.
        with jsonl_log([]) as path:
            with _configured_sink(path.parent / _ABSENT_FILENAME, DB_URL):
                sync_result = _sync_without_dialing(self)
        self.assertEqual(sync_result.inserted, 0)


class ConfiguredFallbackTest(unittest.TestCase):
    """A caller that names neither the source nor the destination gets the
    knobs, read live rather than at import, so the replay follows whichever
    environment the settings were resolved against.
    """

    def test_omitted_inputs_read_the_configured_knobs(self) -> None:
        with jsonl_log([sample_record()]) as path:
            fake = FakeConnection()
            with _configured_sink(path, DB_URL):
                sync_result = run.sync_jsonl_to_postgres(
                    connect=fake.as_connect,
                    json_adapter=keep_payload,
                )
            self.assertEqual(sync_result.inserted, 1)
            _, row_values = fake.inserts[0]
            self.assertEqual(row_values[_SOURCE_PATH_CELL], str(path))


if __name__ == "__main__":
    unittest.main()
