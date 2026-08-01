# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""When the daily rollup is rebuilt, and what a failed rebuild costs the sync."""
from __future__ import annotations

import unittest

from tests.observability.analytics.sync.sync_fake_driver import (
    FakeConnection,
    seed_stored_records,
)
from tests.observability.analytics.sync.sync_test_support import (
    jsonl_log,
    raw_jsonl_log,
    run_sync,
    sample_record,
    sample_records,
    sync_capturing_logs,
)

_REFRESH_STATEMENT = "REFRESH MATERIALIZED VIEW"

_ROLLUP_VIEW = "analytics_daily_rollup"


def _refresh_sqls(connection: FakeConnection) -> list[str]:
    """The rollup rebuilds the run issued, without the statements around them."""
    return [sql for sql, _ in connection.select_calls if _REFRESH_STATEMENT in sql]


class RollupRefreshTest(unittest.TestCase):
    """Every successful commit is followed by a rebuild of the rollup the
    dashboard's window-bounded widgets read, including on a run that inserted
    nothing: rerunning the sync is the documented recovery path for a rollup
    left behind, and gating the rebuild on new rows would take that away. A
    rebuild that fails is logged and swallowed, because the inserts it follows
    are already durable.
    """

    def test_a_successful_insert_rebuilds_the_rollup(self) -> None:
        with jsonl_log([sample_record()]) as path:
            fake = FakeConnection()
            sync_result, log_lines = sync_capturing_logs(self, path, fake)
        self.assertEqual(sync_result.inserted, 1)
        self.assertEqual(len(_refresh_sqls(fake)), 1)
        self.assertIn(_ROLLUP_VIEW, _refresh_sqls(fake)[0])
        # Two commits: the events insert, then the rebuild behind it.
        self.assertEqual(fake.commit_called, 2)
        self.assertEqual(fake.rollback_called, 0)
        joined = "\n".join(log_lines)
        self.assertIn("refreshing materialized view", joined)
        self.assertIn(f"refreshed {_ROLLUP_VIEW}", joined)

    def test_a_duplicate_only_run_still_rebuilds(self) -> None:
        written = sample_records(2)
        with jsonl_log(written) as path:
            fake = FakeConnection()
            seed_stored_records(fake, written)
            sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, 0)
        self.assertEqual(sync_result.skipped_duplicate, len(written))
        self.assertEqual(len(_refresh_sqls(fake)), 1)
        self.assertEqual(fake.commit_called, 2)

    def test_a_malformed_only_file_still_rebuilds(self) -> None:
        # What the file held does not decide whether the operator needs the
        # rollup caught up.
        with raw_jsonl_log(["not json", "null"]) as path:
            fake = FakeConnection()
            sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, 0)
        self.assertEqual(len(_refresh_sqls(fake)), 1)

    def test_a_failed_rebuild_does_not_abort_the_sync(self) -> None:
        # The view not migrated yet, a transient error, a lock-wait timeout:
        # the committed insert is durable regardless, so the run still returns
        # success and the next sync's rebuild recovers the rollup.
        with jsonl_log([sample_record()]) as path:
            fake = FakeConnection()
            fake.raise_on_refresh = RuntimeError("materialized view does not exist")
            sync_result, log_lines = sync_capturing_logs(self, path, fake)
        self.assertEqual(sync_result.inserted, 1)
        # Only the events-insert commit landed; the rebuild raised before its
        # own commit, and the rollback after it is what leaves the connection
        # clean enough to close.
        self.assertEqual(fake.commit_called, 1)
        self.assertEqual(fake.rollback_called, 1)
        self.assertEqual(fake.close_called, 1)
        joined = "\n".join(log_lines)
        self.assertIn(f"refresh of {_ROLLUP_VIEW} failed", joined)
        # The completion line still fires, so a log-scraping operator reads the
        # sync as the success it was.
        self.assertIn("completed in", joined)


if __name__ == "__main__":
    unittest.main()
