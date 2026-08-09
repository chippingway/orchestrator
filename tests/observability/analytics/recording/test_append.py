# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The record envelope, the JSONL line one append writes, and what
intercepts it."""

import contextlib


import json


import tempfile


import unittest


from datetime import datetime


from pathlib import Path


from unittest.mock import patch


from orchestrator.observability.analytics.recording import events

from tests.observability.analytics.analytics_reload_helpers import reload_analytics as _reload


from tests.observability.analytics.analytics_jsonl_helpers import (
    read_lines as _read_lines,
)


_STAGE_KEY = 'stage'


_EVENT_VALUE = 'x'


_REQUIRED_BASE_FIELDS_ISSUE = 42


_REPO_SHORT = "o/r"


_STAGE_IMPLEMENTING = "implementing"


_STAGE_ENTER = "stage_enter"


_ANALYTICS_LOG_PATH = "ANALYTICS_LOG_PATH"


_ANALYTICS_RETENTION_DAYS = "ANALYTICS_RETENTION_DAYS"


_APPEND_RECORD_MEMBER = "append_record"


@contextlib.contextmanager
def _analytics_sink(retention: str | None = None):
    """Re-parse the analytics knobs against a temporary `analytics.jsonl`
    sink, yielding the path every append below lands in.
    """
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "analytics.jsonl"
        env = {_ANALYTICS_LOG_PATH: str(path)}
        if retention is not None:
            env[_ANALYTICS_RETENTION_DAYS] = retention
        _reload(env)
        yield path


class AnalyticsAppendTest(unittest.TestCase):
    """`build_record` produces the documented base fields and
    `append_record` writes one well-formed JSONL line per call.
    """

    def test_record_has_required_base_fields(self) -> None:
        rec = events.build_record(
            repo=_REPO_SHORT,
            issue=_REQUIRED_BASE_FIELDS_ISSUE,
            event=_STAGE_ENTER,
            stage=_STAGE_IMPLEMENTING,
        )
        self.assertIn("ts", rec)
        self.assertEqual(rec["repo"], _REPO_SHORT)
        self.assertEqual(rec["issue"], _REQUIRED_BASE_FIELDS_ISSUE)
        self.assertEqual(rec["event"], _STAGE_ENTER)
        self.assertEqual(rec[_STAGE_KEY], _STAGE_IMPLEMENTING)
        parsed = datetime.fromisoformat(rec["ts"])
        self.assertIsNotNone(parsed.tzinfo)

    def test_stage_omitted_when_none(self) -> None:
        rec = events.build_record(
            repo=_REPO_SHORT,
            issue=1,
            event="pr_opened",
        )
        self.assertNotIn(_STAGE_KEY, rec)

    def test_none_valued_extras_are_dropped(self) -> None:
        rec = events.build_record(
            repo=_REPO_SHORT,
            issue=1,
            event="agent_spawn",
            session_id=None,
            retry_count=2,
        )
        self.assertNotIn("session_id", rec)
        self.assertEqual(rec["retry_count"], 2)

    def test_append_writes_one_line_per_record(self) -> None:
        with _analytics_sink() as path:
            events.append_record(
                events.build_record(
                    repo=_REPO_SHORT,
                    issue=1,
                    event=_STAGE_ENTER,
                    stage=_STAGE_IMPLEMENTING,
                )
            )
            events.append_record(
                events.build_record(
                    repo=_REPO_SHORT,
                    issue=2,
                    event="pr_opened",
                    pr_number=5,
                )
            )
            self.assertTrue(path.exists())
            lines = _read_lines(path)
            self.assertEqual(len(lines), 2)
            rec0 = json.loads(lines[0])
            self.assertEqual(rec0["issue"], 1)
            self.assertEqual(rec0["event"], _STAGE_ENTER)
            self.assertEqual(rec0[_STAGE_KEY], _STAGE_IMPLEMENTING)
            rec1 = json.loads(lines[1])
            self.assertEqual(rec1["pr_number"], 5)
            self.assertNotIn(_STAGE_KEY, rec1)

    def test_creates_missing_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "a" / "b" / "c" / "analytics.jsonl"
            _reload({_ANALYTICS_LOG_PATH: str(path)})
            events.append_record(
                events.build_record(repo=_REPO_SHORT, issue=1, event=_EVENT_VALUE),
            )
            self.assertTrue(path.exists())

    def test_append_is_append_only(self) -> None:
        # Repeated appends must accumulate, never overwrite prior records.
        with _analytics_sink() as path:
            for issue_num in range(5):
                events.append_record(
                    events.build_record(
                        repo=_REPO_SHORT,
                        issue=issue_num,
                        event=_EVENT_VALUE,
                    )
                )
            lines = _read_lines(path)
            self.assertEqual(len(lines), 5)
            issues = [json.loads(line)["issue"] for line in lines]
            self.assertEqual(issues, list(range(5)))


class AppendInterceptionTest(unittest.TestCase):
    """A recorder's own append is dispatched on the owner that defines it, so
    patching it there is what intercepts an internal write.
    """

    def test_internal_append_routes_via_the_owner(self) -> None:
        captured: list[dict] = []
        with patch.object(events, _APPEND_RECORD_MEMBER, captured.append):
            events.record_stage_enter(
                repo=_REPO_SHORT,
                issue=1,
                stage=_STAGE_IMPLEMENTING,
            )
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["event"], _STAGE_ENTER)
