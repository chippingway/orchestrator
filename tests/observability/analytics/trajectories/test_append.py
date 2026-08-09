# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory JSONL append tests."""

import contextlib


import json


import tempfile


import unittest


from functools import partial


from pathlib import Path


from orchestrator.observability.analytics.trajectories import api as trajectory_api
from orchestrator.observability.analytics import sink as analytics_sink

from tests.observability.analytics.analytics_reload_helpers import reload_analytics as _reload


from tests.observability.analytics.analytics_jsonl_helpers import (
    read_lines as _read_lines,
)


from tests.observability.analytics.trajectories.trajectories_test_support import (
    TRAJECTORY_LOG_PATH as _TRAJECTORY_LOG_PATH,
    trajectory_sink as _trajectory_sink,
)

_COUNTER_KEY = 'n'


_ENCODING = "utf-8"


def _logged_call(test_case, logger, action):
    with contextlib.ExitStack() as cleanup:
        captured = cleanup.enter_context(
            test_case.assertLogs(logger, level="WARNING"),
        )
        call_result = action()
    return call_result, list(captured.output)


class TrajectoryAppendTest(unittest.TestCase):
    """`append_trajectory_record` reopens append per record, creates
    parent directories, never overwrites, and downgrades OSError to a
    warning rather than propagating it.
    """

    def test_append_writes_one_line_per_record(self) -> None:
        with _trajectory_sink() as path:
            trajectory_api.append_trajectory_record({"session_id": "a", _COUNTER_KEY: 1})
            trajectory_api.append_trajectory_record({"session_id": "b", _COUNTER_KEY: 2})
            lines = _read_lines(path)
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["session_id"], "a")
            self.assertEqual(json.loads(lines[1])[_COUNTER_KEY], 2)

    def test_creates_missing_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "a" / "b" / "c" / "trajectory.jsonl"
            _reload({_TRAJECTORY_LOG_PATH: str(path)})
            trajectory_api.append_trajectory_record({"event": "x"})
            self.assertTrue(path.exists())

    def test_append_is_append_only(self) -> None:
        with _trajectory_sink() as path:
            for index in range(5):
                trajectory_api.append_trajectory_record({_COUNTER_KEY: index})
            counters = [json.loads(line)[_COUNTER_KEY] for line in _read_lines(path)]
            self.assertEqual(counters, list(range(5)))

    def test_oserror_is_downgraded_to_warning(self) -> None:
        # A path whose parent is a regular file makes `mkdir(parents=True)`
        # raise NotADirectoryError (an OSError). The append must log a
        # warning and swallow it -- analytics/trajectory is observability,
        # never authoritative state, so a misconfigured path cannot raise.
        with tempfile.TemporaryDirectory() as td:
            blocker = Path(td) / "blocker"
            blocker.write_text(
                "i am a file, not a directory",
                encoding=_ENCODING,
            )
            path = blocker / "sub" / "trajectory.jsonl"
            _reload({_TRAJECTORY_LOG_PATH: str(path)})
            _, log_output = _logged_call(
                self,
                analytics_sink.log,
                partial(trajectory_api.append_trajectory_record, {"event": "x"}),
            )
            self.assertFalse(path.exists())
            self.assertTrue(any("could not write" in message for message in log_output))


if __name__ == "__main__":
    unittest.main()
