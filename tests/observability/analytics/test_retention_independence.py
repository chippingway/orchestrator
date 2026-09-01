# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Neither sink's prune may rewrite the other sink's file."""

import tempfile


import unittest


from pathlib import Path


from tests.observability.analytics.analytics_reload_helpers import reload_analytics as _reload


from tests.observability.analytics.analytics_jsonl_helpers import (
    read_text as _read_text,
    write_json_lines as _write_json_lines,
    timestamp_days_ago as _ts_days_ago,
)


from orchestrator.observability.analytics import retention

from tests.observability.analytics import (
    retention_test_support as _support,
)


_PRUNE_NOW = _support.PRUNE_NOW


def _both_sinks(sink_dir: str):
    """Reload the package with both sinks on, equally old, equally pruned."""
    paths = (
        Path(sink_dir) / "analytics.jsonl",
        Path(sink_dir) / "trajectory.jsonl",
    )
    analytics = _reload(
        {
            _support.ANALYTICS_LOG_PATH: str(paths[0]),
            _support.ANALYTICS_RETENTION_DAYS: _support.DEFAULT_RETENTION,
            _support.TRAJECTORY_LOG_PATH: str(paths[1]),
            _support.TRAJECTORY_RETENTION_DAYS: _support.DEFAULT_RETENTION,
        }
    )[1]
    old = _ts_days_ago(_support.VERY_OLD_RECORD_AGE_DAYS, now=_PRUNE_NOW)
    _write_json_lines(paths[0], [{_support.TIMESTAMP_KEY: old, "event": "x"}])
    _write_json_lines(
        paths[1], [{_support.TIMESTAMP_KEY: old, _support.SESSION_ID_KEY: "1"}],
    )
    return analytics, paths


class SinkPruneIndependenceTest(unittest.TestCase):
    """Neither prune rewrites the other sink's file: pruning trajectories
    leaves an equally-old analytics record byte-for-byte alone, and the
    analytics prune leaves the trajectory file alone. The append side of the
    same independence is covered beside its owner under
    `tests/observability/analytics/trajectories/`.
    """

    def test_trajectory_prune_spares_analytics(self) -> None:
        with tempfile.TemporaryDirectory() as sink_dir:
            _analytics, (analytics_path, trajectory_path) = _both_sinks(sink_dir)
            untouched = _read_text(analytics_path)
            self.assertEqual(
                retention.prune_trajectory_records(now=_PRUNE_NOW), 1,
            )
            self.assertEqual(_read_text(trajectory_path), "")
            self.assertEqual(_read_text(analytics_path), untouched)

    def test_analytics_prune_spares_trajectory(self) -> None:
        with tempfile.TemporaryDirectory() as sink_dir:
            _analytics, (analytics_path, trajectory_path) = _both_sinks(sink_dir)
            untouched = _read_text(trajectory_path)
            self.assertEqual(retention.prune_old_records(now=_PRUNE_NOW), 1)
            self.assertEqual(_read_text(analytics_path), "")
            self.assertEqual(_read_text(trajectory_path), untouched)


if __name__ == "__main__":
    unittest.main()
