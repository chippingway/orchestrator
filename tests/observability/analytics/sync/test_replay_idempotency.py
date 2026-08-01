# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What replaying the same file a second time costs the database."""
from __future__ import annotations

import json
import unittest

from tests.observability.analytics.sync.sync_fake_driver import FakeConnection
from tests.observability.analytics.sync.sync_test_support import (
    ENCODING,
    jsonl_log,
    run_sync,
    sample_record,
    sample_records,
)


class RepeatedRunTest(unittest.TestCase):
    """Each record is inserted exactly once however often the file is replayed
    and whatever line it sits on the second time -- the idempotency an
    operator's chosen cadence rests on.
    """

    def test_a_second_run_inserts_nothing(self) -> None:
        written = sample_records(2)
        with jsonl_log(written) as path:
            fake = FakeConnection()
            first = run_sync(path, fake)
            second = run_sync(path, fake)
        self.assertEqual(first.inserted, len(written))
        self.assertEqual(second.inserted, 0)
        self.assertEqual(second.skipped_duplicate, len(written))
        # Only the originals are durably persisted.
        self.assertEqual(len(fake.inserts), len(written))

    def test_renumbered_lines_stay_deduped(self) -> None:
        # After a prune the surviving records move up: a (path, line) key would
        # re-insert them under the freed numbers, and the content hash is what
        # keeps them out.
        written = [
            sample_record(issue=1, event="a"),
            sample_record(issue=2, event="b"),
            sample_record(issue=3, event="c"),
        ]
        kept = written[1:]
        with jsonl_log(written) as path:
            fake = FakeConnection()
            run_sync(path, fake)
            path.write_text(
                "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in kept),
                encoding=ENCODING,
            )
            second = run_sync(path, fake)
        self.assertEqual(second.inserted, 0)
        self.assertEqual(second.skipped_duplicate, len(kept))


if __name__ == "__main__":
    unittest.main()
