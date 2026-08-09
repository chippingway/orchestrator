# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which analytics records a by-age prune drops, and which it must keep."""

import json


import unittest


from datetime import timedelta


from tests.observability.analytics.analytics_jsonl_helpers import (
    read_text as _read_text,
    read_lines as _read_lines,
    write_json_lines as _write_json_lines,
    timestamp_days_ago as _ts_days_ago,
)


from orchestrator.observability.analytics import retention

from tests.observability.analytics import (
    retention_test_support as _support,
)


_EVENT_VALUE = 'x'


_PRUNE_NOW = _support.PRUNE_NOW


def _record(timestamp: str, issue: int, event: str = _EVENT_VALUE) -> dict:
    return {
        _support.TIMESTAMP_KEY: timestamp,
        _support.REPO_KEY: _support.REPO_SHORT,
        _support.ISSUE_KEY: issue,
        _support.EVENT_KEY: event,
    }


class AnalyticsPruneSelectionTest(unittest.TestCase):
    """`prune_old_records` removes records whose `ts` precedes
    `ANALYTICS_RETENTION_DAYS`, keeps newer records, leaves a file with
    nothing old enough byte-for-byte alone, and preserves malformed lines so
    cleanup is operator-driven.
    """

    def test_removes_old_records_keeps_recent(self) -> None:
        old_ts = _ts_days_ago(_support.OLD_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        new_ts = _ts_days_ago(_support.RECENT_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        with _support.analytics_sink(_support.DEFAULT_RETENTION) as path:
            _write_json_lines(
                path,
                [
                    _record(old_ts, 1),
                    _record(new_ts, 2, "y"),
                    _record(old_ts, 3, "z"),
                ],
            )
            self.assertEqual(retention.prune_old_records(now=_PRUNE_NOW), 2)
            remaining = [json.loads(line) for line in _read_lines(path)]
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0][_support.ISSUE_KEY], 2)

    def test_no_records_old_enough_does_not_rewrite(self) -> None:
        new_ts = _ts_days_ago(_support.FRESH_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        with _support.analytics_sink(_support.DEFAULT_RETENTION) as path:
            _write_json_lines(path, [_record(new_ts, 1)])
            mtime_before = path.stat().st_mtime_ns
            self.assertEqual(retention.prune_old_records(now=_PRUNE_NOW), 0)
            self.assertEqual(path.stat().st_mtime_ns, mtime_before)

    def test_malformed_lines_preserved(self) -> None:
        # Non-JSON lines, JSON without `ts`, and unparseable `ts` strings
        # survive the prune so operators can clean up rather than having
        # the helper silently drop data it cannot interpret.
        old_ts = _ts_days_ago(_support.VERY_OLD_RECORD_AGE_DAYS, now=_PRUNE_NOW)
        with _support.analytics_sink(_support.DEFAULT_RETENTION) as path:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding=_support.ENCODING) as fh:
                fh.write("this is not json\n")
                fh.write(f"{json.dumps(_record(old_ts, 1))}\n")
                fh.write('{"ts": "not-a-date", "event": "y"}\n')
                fh.write('{"event": "no-ts-field"}\n')
            # Only the parseable old record is removed; the three other
            # malformed-or-missing-ts lines survive.
            self.assertEqual(retention.prune_old_records(now=_PRUNE_NOW), 1)
            kept = _read_lines(path)
            self.assertEqual(len(kept), 3)
            self.assertIn("this is not json", kept[0])

    def test_naive_timestamp_treated_as_utc(self) -> None:
        # Records written without tz info (or by an older writer) must still
        # be comparable; treat them as UTC rather than raising and aborting
        # the prune.
        old_naive = (
            (_PRUNE_NOW - timedelta(days=_support.OLD_RECORD_AGE_DAYS))
            .replace(tzinfo=None)
            .isoformat(timespec="seconds")
        )
        with _support.analytics_sink(_support.DEFAULT_RETENTION) as path:
            _write_json_lines(path, [_record(old_naive, 1)])
            self.assertEqual(retention.prune_old_records(now=_PRUNE_NOW), 1)
            self.assertEqual(_read_text(path), "")


if __name__ == "__main__":
    unittest.main()
