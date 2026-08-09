# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a written trajectory line is read back as, and what is dismissed."""
from __future__ import annotations

import unittest

from orchestrator.observability.trajectory_viewer import parsing
from tests.observability.analytics.analytics_assertions import assert_row_fields
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    ISSUE,
    TOOL_BASH,
    TOOL_CALL,
    TOOL_EDIT,
    TOOL_RESULT,
    record,
)


_KIND = "kind"

_NAME = "name"

_CONTENT_KEY = "content"

_TOOL_ID = "tool_id"

_ISSUE_FIELD = "issue"

_ROUND_FIELD = "review_round"

_T1 = "t1"

_SKILL_DEVELOP = "develop"

_SEQUENCE = 3


class RecordShapeTest(unittest.TestCase):
    """A written run is read back field for field, its position included."""

    def test_every_written_field_is_read_back(self) -> None:
        run = parsing.parse_record(
            record(
                session_id="sess-1",
                review_round=2,
                retry_count=1,
                user_input="do the thing",
                system_prompt="you are an agent",
                output="done",
                tools=[TOOL_BASH, TOOL_EDIT],
                skills_triggered=[_SKILL_DEVELOP],
                skills_available=[_SKILL_DEVELOP, "review"],
                steps=[
                    {_KIND: TOOL_CALL, _NAME: TOOL_BASH,
                     _TOOL_ID: _T1, _CONTENT_KEY: "ls -la"},
                    {_KIND: TOOL_RESULT, _NAME: None,
                     _TOOL_ID: _T1, _CONTENT_KEY: "listing"},
                ],
                truncated=True,
            ),
            sequence=_SEQUENCE,
        )
        assert run is not None
        assert_row_fields(self, run, {
            "seq": _SEQUENCE,
            _ISSUE_FIELD: ISSUE,
            _ROUND_FIELD: 2,
            "retry_count": 1,
            "tools": (TOOL_BASH, TOOL_EDIT),
            "skills_triggered": (_SKILL_DEVELOP,),
            "truncated": True,
        })
        # A result step's absent name narrows to "" so the page never has to
        # guard against None, and each half of the pair still reports itself.
        self.assertEqual(run.steps[1].name, "")
        self.assertEqual(
            (run.steps[0].is_call, run.steps[1].is_result), (True, True),
        )

    def test_an_unwritten_field_takes_its_default(self) -> None:
        run = parsing.parse_record(record(), sequence=0)
        assert run is not None
        assert_row_fields(self, run, {
            "session_id": "",
            _ROUND_FIELD: None,
            "retry_count": None,
            "tools": (),
            "steps": (),
            "run_usage": None,
            "turns": (),
            "truncated": False,
        })


class DismissedLineTest(unittest.TestCase):
    """Only an object carrying this viewer's own event is read as a run."""

    def test_a_line_this_viewer_does_not_own(self) -> None:
        # The trajectory file is one sink among several a caller may point the
        # reader at, so a foreign event and a bare JSON value are both refused
        # rather than rendered as a run with every field empty.
        for written in (
            "nope",
            ["a", "b"],
            record(event="agent_exit"),
            {"repo": "x", _ISSUE_FIELD: 1},
        ):
            with self.subTest(written=written):
                self.assertIsNone(parsing.parse_record(written, sequence=0))


class RecordCoercionTest(unittest.TestCase):
    """An older or hand-edited field costs a smaller run, never a raise."""

    def test_a_step_with_no_kind_is_dropped(self) -> None:
        # Kind is what a step is read as, so an entry without one -- or one
        # that is not an object at all -- has nothing the page could render.
        run = parsing.parse_record(
            record(steps=[
                {_NAME: TOOL_BASH, _CONTENT_KEY: "x"},
                {_KIND: TOOL_CALL, _NAME: TOOL_EDIT},
                "not-a-dict",
            ]),
            sequence=0,
        )
        assert run is not None
        self.assertEqual([step.name for step in run.steps], [TOOL_EDIT])

    def test_an_absent_body_reads_as_empty(self) -> None:
        run = parsing.parse_record(
            record(steps=[{_KIND: TOOL_RESULT, _TOOL_ID: _T1, _CONTENT_KEY: None}]),
            sequence=0,
        )
        assert run is not None
        self.assertEqual(run.steps[0].content, "")

    def test_a_number_spelled_as_a_string(self) -> None:
        # An issue number that will not narrow falls to 0 rather than dropping
        # the run: the repo, the stage, and the timeline are all still there.
        for field, written, expected in (
            (_ISSUE_FIELD, "7", 7),
            (_ISSUE_FIELD, "bad", 0),
            (_ROUND_FIELD, "3", 3),
        ):
            with self.subTest(field=field, written=written):
                run = parsing.parse_record(
                    record(**{field: written}), sequence=0,
                )
                assert run is not None
                self.assertEqual(getattr(run, field), expected)


if __name__ == "__main__":
    unittest.main()
