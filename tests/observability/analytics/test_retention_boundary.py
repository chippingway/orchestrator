# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""When the analytics prune must do nothing, and what a failed rewrite costs."""

import tempfile


import unittest


from pathlib import Path


from unittest.mock import patch


from tests.analytics_reload_helpers import reload_analytics as _reload


from tests.analytics_jsonl_helpers import (
    read_text as _read_text,
    read_lines as _read_lines,
    write_json_lines as _write_json_lines,
    timestamp_days_ago as _ts_days_ago,
)


from tests.observability.analytics import (
    retention_test_support as _support,
)


_PRUNE_NOW = _support.PRUNE_NOW


# The two spellings of the documented "keep raw data indefinitely" knob: `0` is
# what an operator writes, and any other non-positive value has to mean the
# same thing rather than a negative window nobody can reason about.
_KEEP_FOREVER = ("0", "-5")


def _record(timestamp: str) -> dict:
    return {
        _support.TIMESTAMP_KEY: timestamp,
        _support.REPO_KEY: _support.REPO_SHORT,
        _support.ISSUE_KEY: 1,
        _support.EVENT_KEY: "x",
    }


class AnalyticsPruneBoundaryTest(unittest.TestCase):
    """`prune_old_records` no-ops when retention is non-positive, when the
    sink is disabled, and when the file does not exist -- and a failed
    rewrite leaves the original file untouched rather than truncated.
    """

    def test_non_positive_retention_is_no_op(self) -> None:
        ancient = _ts_days_ago(_support.ANCIENT_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        for retention in _KEEP_FOREVER:
            with self.subTest(retention=retention):
                with _support.analytics_sink(retention) as (path, analytics):
                    _write_json_lines(path, [_record(ancient)])
                    self.assertEqual(
                        analytics.prune_old_records(now=_PRUNE_NOW), 0,
                    )
                    self.assertEqual(len(_read_lines(path)), 1)

    def test_prune_returns_zero_when_disabled(self) -> None:
        # With the sink off, no file is ever opened and the prune is a silent
        # no-op rather than a raise. The append side of the same switch is
        # covered beside its owner under `recording/`.
        _, analytics = _reload({_support.ANALYTICS_LOG_PATH: "off"})
        self.assertEqual(analytics.prune_old_records(), 0)

    def test_missing_file_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as sink_dir:
            path = Path(sink_dir) / "absent.jsonl"
            _, analytics = _reload({_support.ANALYTICS_LOG_PATH: str(path)})
            self.assertEqual(analytics.prune_old_records(), 0)
            self.assertFalse(path.exists())

    def test_rewrite_failure_leaves_original_intact(self) -> None:
        # An OSError from the atomic rewrite (e.g. a full disk hitting
        # `os.replace`) is downgraded to a logged no-op: the prune returns
        # 0 and the original file is left untouched rather than truncated,
        # so analytics stays observability-only. The partial temp file is
        # cleaned up so no `.prune.*.tmp` orphan is left behind.
        old_ts = _ts_days_ago(_support.VERY_OLD_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        with _support.analytics_sink(_support.DEFAULT_RETENTION) as (
            path,
            analytics,
        ):
            _write_json_lines(path, [_record(old_ts)])
            before = _read_text(path)
            with patch.object(
                analytics.os,
                "replace",
                side_effect=OSError("no space left on device"),
            ):
                self.assertEqual(analytics.prune_old_records(now=_PRUNE_NOW), 0)
            self.assertEqual(_read_text(path), before)
            self.assertEqual(
                [entry.name for entry in path.parent.iterdir() if ".prune." in entry.name],
                [],
            )


if __name__ == "__main__":
    unittest.main()
