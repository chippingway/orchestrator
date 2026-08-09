# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A reader built once, answering for whichever environment is in force.

The reader leaf holds the analytics settings holder it captured at its own
import and asks the owner for the knob inside every read. This is what that
buys: re-parsing that holder against a new environment is what the next read
resolves, without the reader being rebuilt or the file being named twice.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orchestrator import trajectory_reader as reader

from tests.analytics_reload_helpers import reload_analytics as _reload

_LOG_PATH_ENV = "TRAJECTORY_LOG_PATH"


class ReparsedEnvironmentTest(unittest.TestCase):
    """Each re-parse is what the already-built reader resolves next."""

    def test_the_reader_follows_each_re_parse(self) -> None:
        with tempfile.TemporaryDirectory() as work_dir:
            first = Path(work_dir) / "a.jsonl"
            second = Path(work_dir) / "b.jsonl"
            _reload({_LOG_PATH_ENV: str(first)})
            resolved_first = reader.resolve_log_path()
            _reload({_LOG_PATH_ENV: str(second)})
            resolved_second = reader.resolve_log_path()
        self.assertEqual((resolved_first, resolved_second), (first, second))


if __name__ == "__main__":
    unittest.main()
