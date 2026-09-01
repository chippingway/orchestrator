# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A read that answers for whichever environment is in force.

The page hands the analytics settings holder to the owner that names the file,
and that owner reads the knob off it inside the call rather than binding it at
its own import. This is what that buys: re-parsing that holder against a new
environment is what the next read resolves, without the page being rebuilt or
the file being named twice.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orchestrator.observability.trajectory_viewer import log_paths

from tests.observability.analytics.analytics_reload_helpers import reload_analytics as _reload

_LOG_PATH_ENV = "TRAJECTORY_LOG_PATH"


def _resolved(log_path: Path) -> Path | None:
    """The file a read names once the holder is re-parsed against it."""
    _, reparsed = _reload({_LOG_PATH_ENV: str(log_path)})
    return log_paths.configured_path(reparsed)


class ReparsedEnvironmentTest(unittest.TestCase):
    """Each re-parse is what the next read through the holder resolves."""

    def test_the_read_follows_each_re_parse(self) -> None:
        with tempfile.TemporaryDirectory() as work_dir:
            named = (Path(work_dir) / "a.jsonl", Path(work_dir) / "b.jsonl")
            resolved = tuple(_resolved(log_path) for log_path in named)
        self.assertEqual(resolved, named)


if __name__ == "__main__":
    unittest.main()
