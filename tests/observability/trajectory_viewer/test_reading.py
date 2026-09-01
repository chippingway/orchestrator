# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one pass over a written trajectory file answers with."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.observability.trajectory_viewer import reading
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    TS,
    record,
)


_READER_LOGGER = "orchestrator.trajectory_reader"

_NEWEST_TS = "2026-06-22T10:00:00+00:00"

_MIDDLE_TS = "2026-06-21T10:00:00+00:00"


def _write_lines(path: Path, lines) -> None:
    """Write each line to `path`: a dict as JSON, a string verbatim."""
    with path.open("w", encoding="utf-8") as trajectory_file:
        for line in lines:
            written = line if isinstance(line, str) else json.dumps(line)
            trajectory_file.write(f"{written}\n")


class _WrittenFileTest(unittest.TestCase):
    """Read back lines written to a file of this test's own."""

    def _read(self, lines) -> list:
        with tempfile.TemporaryDirectory() as work_dir:
            path = Path(work_dir) / "traj.jsonl"
            _write_lines(path, lines)
            return reading.read_trajectories(path)

    def _issues(self, lines) -> list[int]:
        return [run.issue for run in self._read(lines)]


class ReadOrderTest(_WrittenFileTest):
    """Runs come back newest first, with the file's own order as tiebreak."""

    def test_newest_timestamp_comes_back_first(self) -> None:
        self.assertEqual(
            self._issues([
                record(issue=1),
                record(issue=2, ts=_NEWEST_TS),
                record(issue=3, ts=_MIDDLE_TS),
            ]),
            [2, 3, 1],
        )

    def test_same_second_puts_the_later_line_first(self) -> None:
        # Timestamps are second-precision, so the position the line was
        # counted off with is all that separates these two -- and the file is
        # append-only, which makes the one written later the more recent.
        same_second = [
            record(issue=1, ts=TS),
            record(issue=2, ts=TS),
        ]
        self.assertEqual(self._issues(same_second), [2, 1])


class SkippedLineTest(_WrittenFileTest):
    """A line this viewer cannot use costs its own row and nothing more."""

    def test_unusable_lines_are_skipped(self) -> None:
        issues = self._issues([
            record(issue=1),
            "",
            "{not valid json",
            record(issue=2, event="agent_exit"),
            record(issue=3),
        ])
        self.assertEqual(set(issues), {1, 3})

    def test_a_skipped_line_still_costs_a_position(self) -> None:
        # The position is what two same-second records are ordered by, and it
        # is counted off the file rather than off the records kept.
        written = [
            "",
            record(issue=1),
            record(issue=2),
        ]
        positions = [run.seq for run in self._read(written)]
        self.assertEqual(positions, [2, 1])


class UnreadableFileTest(unittest.TestCase):
    """A file the read cannot open leaves the page up either way."""

    def test_a_disabled_sink_reads_as_no_runs(self) -> None:
        self.assertEqual(reading.read_trajectories(None), [])

    def test_a_missing_file_reads_as_no_runs(self) -> None:
        # What a sink switched on but not yet written to looks like, so it is
        # answered silently rather than warned about.
        with tempfile.TemporaryDirectory() as work_dir:
            path = Path(work_dir) / "absent.jsonl"
            self.assertEqual(reading.read_trajectories(path), [])

    def test_an_unreadable_file_warns_and_reads_empty(self) -> None:
        # A directory raises `IsADirectoryError` -- an `OSError` that is not
        # `FileNotFoundError` -- so the read takes the warn-and-empty branch.
        # The warning carries the `orchestrator.trajectory_reader` name an
        # operator's log filter is keyed on.
        with tempfile.TemporaryDirectory() as work_dir:
            with self.assertLogs(_READER_LOGGER, level="WARNING") as captured:
                self.assertEqual(reading.read_trajectories(Path(work_dir)), [])
                self.assertEqual(
                    [entry.name for entry in captured.records],
                    [_READER_LOGGER],
                )
                self.assertIn(
                    "could not read trajectory log", captured.output[0],
                )


if __name__ == "__main__":
    unittest.main()
