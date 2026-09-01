# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What an operator watching a long replay sees while it advances."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.observability.analytics.sync import ingest
from tests.observability.analytics.sync.sync_fake_driver import FakeConnection
from tests.observability.analytics.sync.sync_test_support import (
    jsonl_log,
    sample_record,
    sample_records,
    sync_capturing_logs,
)

_BATCH_SIZE_ATTR = "BATCH_SIZE"

_TEST_BATCH_SIZE = 3

_PROGRESS_MARKER = "progress lines="

_ABSENT_FILENAME = "never-written.jsonl"


def _progress_lines(log_lines: list[str]) -> list[str]:
    """The per-flush records, without the connect and completion lines."""
    return [line for line in log_lines if _PROGRESS_MARKER in line]


class ProgressLogTest(unittest.TestCase):
    """One progress record drops after every batched flush -- full buffer or
    the partial one at EOF -- carrying the counts consumed so far, and the run
    ends on a line naming its wall-clock. An operator's "did the tail land?"
    must not depend on the record count dividing the buffer size.
    """

    def test_one_record_per_full_flush(self) -> None:
        written = sample_records(_TEST_BATCH_SIZE * 2)
        with jsonl_log(written) as path:
            with patch.object(ingest, _BATCH_SIZE_ATTR, _TEST_BATCH_SIZE):
                _, log_lines = sync_capturing_logs(self, path, FakeConnection())
        progress_lines = _progress_lines(log_lines)
        self.assertEqual(len(progress_lines), 2)
        # Each record fires after its flush, so the counts are cumulative.
        self.assertIn(f"lines={_TEST_BATCH_SIZE}", progress_lines[0])
        self.assertIn(f"lines={len(written)}", progress_lines[1])

    def test_the_partial_flush_reports_too(self) -> None:
        written = sample_records(_TEST_BATCH_SIZE + 2)
        with jsonl_log(written) as path:
            with patch.object(ingest, _BATCH_SIZE_ATTR, _TEST_BATCH_SIZE):
                _, log_lines = sync_capturing_logs(self, path, FakeConnection())
        progress_lines = _progress_lines(log_lines)
        self.assertEqual(len(progress_lines), 2)
        self.assertIn(f"inserted={_TEST_BATCH_SIZE}", progress_lines[0])
        self.assertIn(f"lines={len(written)}", progress_lines[1])
        self.assertIn(f"inserted={len(written)}", progress_lines[1])

    def test_the_completion_line_carries_the_duration(self) -> None:
        with jsonl_log([sample_record()]) as path:
            sync_result, log_lines = sync_capturing_logs(self, path, FakeConnection())
        self.assertIn("completed in", "\n".join(log_lines))
        # The result carries the same wall-clock, so the CLI prints it without
        # timing the call a second time.
        self.assertGreaterEqual(sync_result.duration_s, float(0))

    def test_a_no_op_never_claims_a_connection(self) -> None:
        # The connect pair implies a dial actually happened, so a configured
        # no-op must not log it.
        with jsonl_log([]) as path:
            _, log_lines = sync_capturing_logs(
                self, path.parent / _ABSENT_FILENAME, FakeConnection(),
            )
        joined = "\n".join(log_lines)
        self.assertNotIn("connecting to", joined)
        self.assertNotIn("connection established", joined)


if __name__ == "__main__":
    unittest.main()
