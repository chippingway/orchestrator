# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a line the table would reject costs the replay of the lines around it."""
from __future__ import annotations

import unittest
from datetime import timezone

from orchestrator.observability.analytics.sync import columns
from tests.observability.analytics.sync.sync_fake_driver import FakeConnection
from tests.observability.analytics.sync.sync_test_support import (
    ENCODING,
    jsonl_log,
    raw_jsonl_log,
    record_line,
    run_sync,
    sample_record,
)

_NAIVE_TS = "2026-05-25T12:00:00"

_MISSING_KEY_LINES = (
    '{"repo": "o/r", "issue": 1, "event": "x"}',
    '{"ts": "2026-05-25T12:00:00+00:00", "issue": 1, "event": "x"}',
    '{"ts": "2026-05-25T12:00:00+00:00", "repo": "o/r", "event": "x"}',
    '{"ts": "2026-05-25T12:00:00+00:00", "repo": "o/r", "issue": 1}',
)


class MalformedLineTest(unittest.TestCase):
    """A line that cannot become a row is counted and logged, never raised, so
    the good lines around it still land. Blank lines are not a failure at all,
    and the JSONL file is read-only whatever it holds -- cleanup is the
    operator's, out of band.
    """

    def test_blank_lines_are_not_counted_malformed(self) -> None:
        with raw_jsonl_log(["", record_line(), "   "]) as path:
            fake = FakeConnection()
            sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, 1)
        self.assertEqual(sync_result.skipped_malformed, 0)
        self.assertEqual(sync_result.total_lines, 3)

    def test_a_non_json_line_is_counted_and_skipped(self) -> None:
        with raw_jsonl_log(["this is not json", record_line()]) as path:
            fake = FakeConnection()
            sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, 1)
        self.assertEqual(sync_result.skipped_malformed, 1)
        self.assertEqual(sync_result.malformed_line_numbers, (1,))
        # The record on line 2 still lands: one bad line cannot poison the
        # batch the lines around it ride.
        self.assertEqual(len(fake.inserts), 1)

    def test_json_that_is_not_an_object_is_skipped(self) -> None:
        # `null`, lists, and numbers parse cleanly but carry no record.
        with raw_jsonl_log(["null", "[1, 2, 3]", "42", record_line()]) as path:
            fake = FakeConnection()
            sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, 1)
        self.assertEqual(sync_result.skipped_malformed, 3)

    def test_a_missing_required_key_is_skipped(self) -> None:
        # The four columns are NOT NULL, so the record is filtered here rather
        # than left for psycopg to raise on mid-transaction.
        with raw_jsonl_log([*_MISSING_KEY_LINES, record_line()]) as path:
            fake = FakeConnection()
            sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, 1)
        self.assertEqual(sync_result.skipped_malformed, len(_MISSING_KEY_LINES))

    def test_an_unusable_ts_leaves_the_file_alone(self) -> None:
        lines = ['{"ts": "not-a-date", "repo": "o/r", "issue": 1, "event": "x"}', record_line()]
        with raw_jsonl_log(lines) as path:
            fake = FakeConnection()
            sync_result = run_sync(path, fake)
            preserved = path.read_text(encoding=ENCODING).splitlines()
        self.assertEqual(sync_result.inserted, 1)
        self.assertEqual(sync_result.skipped_malformed, 1)
        self.assertEqual(len(preserved), len(lines))

    def test_a_naive_timestamp_reads_as_utc(self) -> None:
        # A record written without an offset still lands, read the way the
        # prune reads one, rather than being rejected as malformed.
        with jsonl_log([sample_record(ts=_NAIVE_TS)]) as path:
            fake = FakeConnection()
            sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, 1)
        _, row_values = fake.inserts[0]
        ts_cell = row_values[columns.PROMOTED_COLUMNS.index("ts")]
        self.assertEqual(ts_cell.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
