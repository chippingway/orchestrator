# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The trajectory sink's own prune: its own knobs, the same shared core."""

import contextlib


import json


import tempfile


import unittest


from datetime import timedelta


from pathlib import Path


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


_ONE_TEXT = '1'


_PRUNE_NOW = _support.PRUNE_NOW


# A single path component well past NAME_MAX (255), which makes the underlying
# stat() raise OSError [Errno 36] File name too long.
_OVERLONG_NAME_LENGTH = 5000


# Both spellings of the "keep trajectories indefinitely" knob.
_KEEP_FOREVER = ("0", "-5")


# Every way the opt-in sink can be off: never set, and a disable sentinel.
_SINK_OFF = (None, "disabled")


def _record(timestamp: str, session_id: str = _ONE_TEXT) -> dict:
    return {
        _support.TIMESTAMP_KEY: timestamp,
        _support.SESSION_ID_KEY: session_id,
    }


def _logged_call(test_case, logger, action):
    with contextlib.ExitStack() as cleanup:
        captured = cleanup.enter_context(
            test_case.assertLogs(logger, level="WARNING"),
        )
        call_result = action()
    return call_result, list(captured.output)


class TrajectoryPruneSelectionTest(unittest.TestCase):
    """`prune_trajectory_records` mirrors `prune_old_records`: it removes
    records past `TRAJECTORY_RETENTION_DAYS`, leaves a file with nothing old
    enough alone, and preserves malformed / unparseable lines.
    """

    def test_removes_old_records_keeps_recent(self) -> None:
        old_ts = _ts_days_ago(_support.OLD_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        new_ts = _ts_days_ago(_support.RECENT_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        with _support.trajectory_sink(_support.DEFAULT_RETENTION) as (
            path,
            analytics,
        ):
            _write_json_lines(
                path,
                [_record(old_ts), _record(new_ts, "2"), _record(old_ts, "3")],
            )
            self.assertEqual(
                analytics.prune_trajectory_records(now=_PRUNE_NOW), 2,
            )
            self.assertEqual(
                [
                    json.loads(line)[_support.SESSION_ID_KEY]
                    for line in _read_lines(path)
                ],
                ["2"],
            )

    def test_no_records_old_enough_does_not_rewrite(self) -> None:
        new_ts = _ts_days_ago(_support.FRESH_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        with _support.trajectory_sink(_support.DEFAULT_RETENTION) as (
            path,
            analytics,
        ):
            _write_json_lines(path, [_record(new_ts)])
            mtime_before = path.stat().st_mtime_ns
            self.assertEqual(
                analytics.prune_trajectory_records(now=_PRUNE_NOW), 0,
            )
            self.assertEqual(path.stat().st_mtime_ns, mtime_before)

    def test_malformed_lines_preserved(self) -> None:
        old_ts = _ts_days_ago(_support.VERY_OLD_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        with _support.trajectory_sink(_support.DEFAULT_RETENTION) as (
            path,
            analytics,
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding=_support.ENCODING) as fh:
                fh.write("this is not json\n")
                fh.write(f"{json.dumps(_record(old_ts))}\n")
                fh.write('{"ts": "not-a-date", "session_id": "2"}\n')
                fh.write('{"session_id": "no-ts-field"}\n')
            self.assertEqual(
                analytics.prune_trajectory_records(now=_PRUNE_NOW), 1,
            )
            kept = _read_lines(path)
            self.assertEqual(len(kept), 3)
            self.assertIn("this is not json", kept[0])

    def test_naive_timestamp_treated_as_utc(self) -> None:
        old_naive = (
            (_PRUNE_NOW - timedelta(days=_support.OLD_RECORD_AGE_DAYS))
            .replace(tzinfo=None)
            .isoformat(timespec="seconds")
        )
        with _support.trajectory_sink(_support.DEFAULT_RETENTION) as (
            path,
            analytics,
        ):
            _write_json_lines(path, [_record(old_naive)])
            self.assertEqual(
                analytics.prune_trajectory_records(now=_PRUNE_NOW), 1,
            )
            self.assertEqual(_read_text(path), "")


class TrajectoryPruneBoundaryTest(unittest.TestCase):
    """`prune_trajectory_records` no-ops at retention <= 0, on an absent
    file, and whenever the opt-in sink is off -- unset or disabled -- and
    downgrades an unusable path to a warning rather than raising into the
    caller.
    """

    def test_prune_returns_zero_when_sink_is_off(self) -> None:
        for spelling in _SINK_OFF:
            environment = {}
            if spelling is not None:
                environment = {_support.TRAJECTORY_LOG_PATH: spelling}
            with self.subTest(sink=spelling):
                _, analytics = _reload(environment)
                self.assertEqual(analytics.prune_trajectory_records(), 0)

    def test_non_positive_retention_is_no_op(self) -> None:
        ancient = _ts_days_ago(_support.ANCIENT_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        for retention in _KEEP_FOREVER:
            with self.subTest(retention=retention):
                with _support.trajectory_sink(retention) as (path, analytics):
                    _write_json_lines(path, [_record(ancient)])
                    self.assertEqual(
                        analytics.prune_trajectory_records(now=_PRUNE_NOW), 0,
                    )
                    self.assertEqual(len(_read_lines(path)), 1)

    def test_missing_file_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as sink_dir:
            path = Path(sink_dir) / "absent.jsonl"
            _, analytics = _reload({_support.TRAJECTORY_LOG_PATH: str(path)})
            self.assertEqual(analytics.prune_trajectory_records(), 0)
            self.assertFalse(path.exists())

    def test_probe_oserror_becomes_warning(self) -> None:
        # `Path.exists()` re-raises OSErrors that don't mean "absent"
        # (e.g. ENAMETOOLONG on an over-long path). That probe runs
        # before the read/rewrite try-block, so without its own guard
        # the error would escape the per-tick caller. The prune must
        # warn and no-op (return 0) instead of raising.
        with tempfile.TemporaryDirectory() as sink_dir:
            path = Path(sink_dir) / ("x" * _OVERLONG_NAME_LENGTH)
            _, analytics = _reload(
                {
                    _support.TRAJECTORY_LOG_PATH: str(path),
                    _support.TRAJECTORY_RETENTION_DAYS: _support.DEFAULT_RETENTION,
                }
            )
            removed, log_output = _logged_call(
                self,
                analytics.log,
                analytics.prune_trajectory_records,
            )
            self.assertEqual(removed, 0)
            self.assertTrue(any("prune" in message for message in log_output))


if __name__ == "__main__":
    unittest.main()
