# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics sync configuration and disabled-path tests."""

import unittest


from tests.analytics_sync_reload import (
    reload_sync as _reload,
    reloaded_sync as _reloaded_sync,
    sync_for_records as _sync_for_records,
)

from tests.analytics_sync_fakes import (
    FakeConnection as _FakeConnection,
)

from tests.analytics_sync_payloads import (
    sample_record as _sample_record,
)


SAMPLE_TIMESTAMP = "2026-05-25T12:00:00+00:00"


_STAGE_ENTER = "stage_enter"


_ISSUE_KEY = "issue"


_LOG_PATH_ENV = "ANALYTICS_LOG_PATH"


_DB_URL_ENV = "ANALYTICS_DB_URL"


_SENTINEL_DISABLED = "off"


_DB_URL = "postgresql://h/db"


_SYNC_MODULE = "orchestrator.analytics.sync"


_REFRESH_STMT = "REFRESH MATERIALIZED VIEW"


_LOG_FILENAME = "a.jsonl"


_ENCODING = "utf-8"


_Batch = tuple[str, list[tuple]]


class AnalyticsSyncDisabledTest(unittest.TestCase):
    """When either env knob is unset the sync is a silent no-op: no
    connection attempt, no row insertion, no error. Mirrors how
    `analytics.append_record` no-ops when the sink is disabled.
    """

    def test_no_op_when_db_url_unset(self) -> None:
        records = [_sample_record()]
        with _sync_for_records(records, db_url="") as (_, analytics_sync):
            connected = []
            sync_result = analytics_sync.sync_jsonl_to_postgres(
                connect=lambda url: connected.append(url) or _FakeConnection(),
            )
            self.assertEqual(connected, [])
            self.assertEqual(sync_result.inserted, 0)
            self.assertEqual(sync_result.total_lines, 0)

    def test_no_op_when_log_path_unset(self) -> None:
        _, analytics_sync = _reload(
            {
                _LOG_PATH_ENV: _SENTINEL_DISABLED,
                _DB_URL_ENV: _DB_URL,
            }
        )
        connected = []
        sync_result = analytics_sync.sync_jsonl_to_postgres(
            connect=lambda url: connected.append(url) or _FakeConnection(),
        )
        self.assertEqual(connected, [])
        self.assertEqual(sync_result.inserted, 0)

    def test_no_op_when_log_file_missing(self) -> None:
        # Configured but file not created yet (orchestrator hasn't
        # emitted any record). Don't connect, don't fail. The no-op
        # writer leaves the path absent so the sync sees a missing file.
        with _reloaded_sync(lambda path: None) as (_, analytics_sync):
            connected = []
            sync_result = analytics_sync.sync_jsonl_to_postgres(
                connect=lambda url: connected.append(url) or _FakeConnection(),
            )
            self.assertEqual(connected, [])
            self.assertEqual(sync_result.inserted, 0)
