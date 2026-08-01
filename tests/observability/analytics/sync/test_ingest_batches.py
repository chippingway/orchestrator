# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How many round-trips one file's rows cost, and what the driver reports back."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.observability.analytics.sync import ingest
from orchestrator.observability.analytics.sync.models import SyncCounters
from tests.observability.analytics.sync.sync_fake_driver import (
    FakeConnection,
    NegativeRowcountCursor,
    RejectingBatchCursor,
    seed_stored_records,
)
from tests.observability.analytics.sync.sync_test_support import (
    jsonl_log,
    run_sync,
    sample_record,
    sample_records,
)

_BATCH_SIZE_ATTR = "BATCH_SIZE"

_TEST_BATCH_SIZE = 3

_PARTIAL_BATCH_RECORD_COUNT = _TEST_BATCH_SIZE + 2

_INSERT_STATEMENT = "INSERT ..."


def _only_batch(connection: FakeConnection) -> list[tuple]:
    """The rows of the single batch the run flushed."""
    return connection.batches[0][1]


class BatchedInsertTest(unittest.TestCase):
    """Validated rows accumulate into a buffer of the configured size, each
    full buffer reaches the driver as one `executemany`, and the partial buffer
    left at EOF still lands -- a multi-thousand-record replay must not drop its
    tail, and must not pay a round-trip per row to keep it.
    """

    def test_a_full_buffer_is_one_executemany(self) -> None:
        with jsonl_log(sample_records(_TEST_BATCH_SIZE)) as path:
            fake = FakeConnection()
            with patch.object(ingest, _BATCH_SIZE_ATTR, _TEST_BATCH_SIZE):
                sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, _TEST_BATCH_SIZE)
        self.assertEqual(sync_result.skipped_duplicate, 0)
        self.assertEqual(len(fake.batches), 1)
        sql, batch_rows = fake.batches[0]
        self.assertEqual(len(batch_rows), _TEST_BATCH_SIZE)
        self.assertIn("ON CONFLICT (content_hash) DO NOTHING", sql)

    def test_the_partial_buffer_flushes_at_eof(self) -> None:
        written = sample_records(_PARTIAL_BATCH_RECORD_COUNT)
        with jsonl_log(written) as path:
            fake = FakeConnection()
            with patch.object(ingest, _BATCH_SIZE_ATTR, _TEST_BATCH_SIZE):
                sync_result = run_sync(path, fake)
        tail_size = len(written) - _TEST_BATCH_SIZE
        self.assertEqual(sync_result.inserted, len(written))
        self.assertEqual(len(fake.batches), 2)
        self.assertEqual(len(fake.batches[0][1]), _TEST_BATCH_SIZE)
        self.assertEqual(len(fake.batches[1][1]), tail_size)
        # Two commits: the events insert, then the one behind the refresh.
        self.assertEqual(fake.commit_called, 2)

    def test_fewer_records_than_the_buffer_flush(self) -> None:
        with jsonl_log([sample_record()]) as path:
            fake = FakeConnection()
            sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, 1)
        self.assertEqual(len(fake.batches), 1)
        self.assertEqual(len(_only_batch(fake)), 1)

    def test_a_file_with_no_record_never_flushes(self) -> None:
        # The wire stays quiet, but the transaction still commits so the
        # implicit one is released and the refresh behind it still fires.
        with jsonl_log([]) as path:
            fake = FakeConnection()
            sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, 0)
        self.assertEqual(len(fake.batches), 0)
        self.assertEqual(fake.commit_called, 2)


class FlushRowcountTest(unittest.TestCase):
    """The driver's per-`executemany` rowcount is what one batch is split back
    into inserted and duplicate by, so the tallies stay right even where the
    startup scan could not have known what the batch would hit.
    """

    def test_rowcount_splits_inserted_from_duplicate(self) -> None:
        # A writer that landed rows AFTER the startup scan answered: the scan
        # reads an empty database while the stored set already holds two of the
        # hashes. Every row still reaches `executemany`, and the rowcount is
        # what tells the sync how many of them the arbiter actually took.
        written = sample_records(_TEST_BATCH_SIZE + 1)
        with jsonl_log(written) as path:
            fake = FakeConnection()
            fake.pre_check_hashes = set()
            racing = written[:2]
            seed_stored_records(fake, racing)
            with patch.object(ingest, _BATCH_SIZE_ATTR, len(written)):
                sync_result = run_sync(path, fake)
        self.assertEqual(sync_result.inserted, len(written) - len(racing))
        self.assertEqual(sync_result.skipped_duplicate, len(racing))
        self.assertEqual(len(fake.batches), 1)
        self.assertEqual(len(_only_batch(fake)), len(written))

    def test_a_stripped_rowcount_counts_inserted(self) -> None:
        # A driver reporting -1 leaves `inserted` a lower bound rather than
        # letting the duplicate arithmetic run negative.
        cursor = NegativeRowcountCursor()
        counters = SyncCounters()
        batch = [("a",), ("b",), ("c",)]
        ingest.flush_batch(cursor, _INSERT_STATEMENT, batch, counters, start=float())
        self.assertEqual(counters.inserted, len(cursor.calls[0]))
        self.assertEqual(counters.skipped_duplicate, 0)
        # The buffer is cleared so the caller can refill it, and the whole
        # batch reached the wire in a single call.
        self.assertEqual(batch, [])
        self.assertEqual(len(cursor.calls), 1)

    def test_an_empty_batch_never_reaches_the_driver(self) -> None:
        counters = SyncCounters()
        ingest.flush_batch(
            RejectingBatchCursor(), _INSERT_STATEMENT, [], counters, start=float(),
        )
        self.assertEqual(counters.inserted, 0)
        self.assertEqual(counters.skipped_duplicate, 0)


if __name__ == "__main__":
    unittest.main()
