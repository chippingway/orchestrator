# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a trajectory append costs the analytics sink: nothing at all."""

import tempfile


import unittest


from pathlib import Path


from orchestrator.observability.analytics import sink as analytics_sink
from orchestrator.observability.analytics.trajectories import api as trajectory_api

from tests.analytics_reload_helpers import reload_analytics as _reload


from tests.observability.analytics.trajectories.trajectories_test_support import (
    ANALYTICS_FILENAME,
    ANALYTICS_LOG_PATH as _ANALYTICS_LOG_PATH,
    TRAJECTORY_FILENAME,
    TRAJECTORY_LOG_PATH as _TRAJECTORY_LOG_PATH,
)


class TrajectoryAppendIndependenceTest(unittest.TestCase):
    """The trajectory sink is a fully independent file: its append never
    opens or writes `ANALYTICS_LOG_PATH`, and it holds a dedicated lock so
    the two sinks do not serialize against one another. The prune side of the
    same independence is covered beside its owner in
    `tests/observability/analytics/test_retention_independence.py`.
    """

    def test_dedicated_lock_is_distinct(self) -> None:
        self.assertIsNot(
            analytics_sink.ANALYTICS_FILE_LOCK,
            analytics_sink.TRAJECTORY_FILE_LOCK,
        )

    def test_append_leaves_analytics_file_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            a_path = Path(td) / ANALYTICS_FILENAME
            t_path = Path(td) / TRAJECTORY_FILENAME
            _reload(
                {
                    _ANALYTICS_LOG_PATH: str(a_path),
                    _TRAJECTORY_LOG_PATH: str(t_path),
                }
            )
            trajectory_api.append_trajectory_record({"session_id": "s"})
            self.assertTrue(t_path.exists())
            # The analytics file was never opened by the trajectory append.
            self.assertFalse(a_path.exists())


if __name__ == "__main__":
    unittest.main()
