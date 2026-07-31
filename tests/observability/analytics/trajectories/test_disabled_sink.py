# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a trajectory append costs while the sink is off: nothing on disk."""

import tempfile


import unittest


from pathlib import Path


from tests.analytics_reload_helpers import reload_analytics as _reload


from tests.observability.analytics.trajectories.trajectories_test_support import (
    TRAJECTORY_LOG_PATH as _TRAJECTORY_LOG_PATH,
)


class TrajectoryDisabledSinkAppendTest(unittest.TestCase):
    """With the trajectory sink disabled -- which is the opt-in default, not
    just an explicit `off` -- `append_trajectory_record` is a silent no-op: no
    file is ever opened and the helper does not raise. The prune side of the
    same switch is covered beside its owner in
    `tests/observability/analytics/test_retention_trajectory.py`.
    """

    def test_append_creates_no_file_when_unset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _, analytics = _reload()  # TRAJECTORY_LOG_PATH unset => off
            analytics.append_trajectory_record({"ts": "x", "event": "y"})
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_append_creates_no_file_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sentinel = Path(td) / "must-not-be-created.jsonl"
            _, analytics = _reload({_TRAJECTORY_LOG_PATH: "off"})
            analytics.append_trajectory_record({"ts": "x", "event": "y"})
            self.assertFalse(sentinel.exists())
            self.assertEqual(list(Path(td).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
