# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics trajectory source-item accounting tests."""

import json


import tempfile


import unittest


from pathlib import Path


from tests.observability.analytics.analytics_jsonl_helpers import (
    read_records as _read_records,
)


from tests.observability.analytics.analytics_codex_item_cases import (
    CODEX_ACCOUNTED_ITEMS,
    CODEX_ACCOUNTING_COUNTS,
    CODEX_ACCOUNTING_OUTPUT,
    CODEX_ACCOUNTING_STEP_COUNT,
    CODEX_HIDDEN_REASONING_TEXT,
    codex_accounting_stdout as _codex_accounting_stdout,
)


from tests.observability.analytics.analytics_trajectory_cases import (
    claude_trajectory_stdout as _claude_trajectory_stdout,
)


from tests.observability.analytics.trajectories import (
    trajectories_test_support as _support,
)

_ANALYTICS_FILENAME_ALTERNATE = _support.ANALYTICS_FILENAME_ALTERNATE


_CODEX = _support.CODEX


_DISPOSITION_KEY = _support.DISPOSITION_KEY


_ITEM_ID_KEY = _support.ITEM_ID_KEY


_ITEM_TYPE_KEY = _support.ITEM_TYPE_KEY


_OUTPUT_KEY = _support.OUTPUT_KEY


_PROMPT_TEXT = _support.PROMPT_TEXT


_SOURCE_ITEM_COUNTS_KEY = _support.SOURCE_ITEM_COUNTS_KEY


_SOURCE_ITEMS_KEY = _support.SOURCE_ITEMS_KEY


_SOURCE_ITEMS_TRUNCATED_KEY = _support.SOURCE_ITEMS_TRUNCATED_KEY


_STEPS_KEY = _support.STEPS_KEY


_TRAJECTORY_FILENAME = _support.TRAJECTORY_FILENAME


_TRUNCATED_KEY = _support.TRUNCATED_KEY


def accounting_rows(record: dict) -> tuple:
    """The record's accounting as `(item_id, item_type, disposition)` rows."""
    return tuple(
        (row[_ITEM_ID_KEY], row[_ITEM_TYPE_KEY], row[_DISPOSITION_KEY])
        for row in record[_SOURCE_ITEMS_KEY]
    )


class RecordAgentExitItemAccountingTest(_support.RecordAgentExitTrajectorySupport):
    """What one codex run's identified items are recorded as."""

    def test_identified_items_recorded_in_order(self) -> None:
        # One row per id the stream identified, in first-seen order, so an
        # item type nothing normalizes is auditable wherever it fell --
        # including immediately before the message that ends the run and
        # after it, the two placements where the ordered steps alone cannot
        # say whether the parser reached the item at all.
        with tempfile.TemporaryDirectory() as sink_dir:
            record = self._emit_accounting_record(sink_dir)
            self.assertEqual(accounting_rows(record), CODEX_ACCOUNTED_ITEMS)

    def test_whole_accounting_carries_counts(self) -> None:
        # An accounting the budget left whole says so: the counts total every
        # disposition the run produced and neither truncation flag is written.
        with tempfile.TemporaryDirectory() as sink_dir:
            record = self._emit_accounting_record(sink_dir)
            self.assertEqual(
                record[_SOURCE_ITEM_COUNTS_KEY],
                dict(CODEX_ACCOUNTING_COUNTS),
            )
            self.assertNotIn(_SOURCE_ITEMS_TRUNCATED_KEY, record)
            self.assertNotIn(_TRUNCATED_KEY, record)

    def test_excluded_item_named_without_its_text(self) -> None:
        # The reasoning exclusion is recorded as an id, a type, and a
        # disposition; the hidden text behind it never enters the record. The
        # accounting names every item, the timeline only the ones that
        # contributed -- the excluded and empty items contribute no step, the
        # two unsupported ones their placeholders, and the run ends on its
        # answer.
        with tempfile.TemporaryDirectory() as sink_dir:
            record = self._emit_accounting_record(sink_dir)
            self.assertNotIn(CODEX_HIDDEN_REASONING_TEXT, json.dumps(record))
            self.assertEqual(
                len(record[_STEPS_KEY]),
                CODEX_ACCOUNTING_STEP_COUNT,
            )
            self.assertEqual(record[_OUTPUT_KEY], CODEX_ACCOUNTING_OUTPUT)

    def test_item_less_stream_writes_no_accounting(self) -> None:
        # Claude's stream identifies no codex items, so all three accounting
        # fields are left off rather than written empty: a reader of a
        # non-codex record meets no accounting key at all.
        with tempfile.TemporaryDirectory() as sink_dir:
            trajectory_path = Path(sink_dir) / _TRAJECTORY_FILENAME
            self._emit(
                stdout=_claude_trajectory_stdout(),
                prompt=_PROMPT_TEXT,
                traj_path=trajectory_path,
                analytics_path=Path(sink_dir) / _ANALYTICS_FILENAME_ALTERNATE,
            )
            record = _read_records(trajectory_path)[0]
            for absent in (
                _SOURCE_ITEMS_KEY,
                _SOURCE_ITEM_COUNTS_KEY,
                _SOURCE_ITEMS_TRUNCATED_KEY,
            ):
                with self.subTest(field=absent):
                    self.assertNotIn(absent, record)

    def _emit_accounting_record(self, sink_dir: str) -> dict:
        trajectory_path = Path(sink_dir) / _TRAJECTORY_FILENAME
        self._emit(
            backend=_CODEX,
            stdout=_codex_accounting_stdout(),
            prompt=_PROMPT_TEXT,
            traj_path=trajectory_path,
            analytics_path=Path(sink_dir) / _ANALYTICS_FILENAME_ALTERNATE,
        )
        return _read_records(trajectory_path)[0]


if __name__ == "__main__":
    unittest.main()
