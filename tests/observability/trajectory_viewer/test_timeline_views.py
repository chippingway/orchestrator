# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The sequence a run renders as, the name it is picked by, and what hides it."""
from __future__ import annotations

import unittest

from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    ASSISTANT_MESSAGE,
    TOOL_BASH,
    TOOL_CALL,
    TOOL_RESULT,
    TOOL_SKILL,
    run,
    step,
)


_PROMPT = "prompt"

_OUTPUT = "output"

_ASKED = "do the thing"

_ANSWERED = "all done"

_TOOL_ID = "t1"

_STAGE = "implementing"

_ROLE = "developer"

_BACKEND = "claude"

_FIXTURE_PROMPT = "ignored"

_SKILL_DEVELOP = "develop"


class TimelineAssemblyTest(unittest.TestCase):
    """Two record vintages are read back as one ordered sequence."""

    def test_steps_bracketed_by_prompt_and_output(self) -> None:
        # An older record carries only tool work, a newer one interleaves text
        # turns among it, and both render as prompt, stream order, output.
        bracketed = run(
            user_input=_ASKED,
            output=_ANSWERED,
            steps=(
                step(ASSISTANT_MESSAGE, content="let me look"),
                step(TOOL_CALL, name=TOOL_BASH, tool_id=_TOOL_ID, content="ls"),
                step(TOOL_RESULT, tool_id=_TOOL_ID, content="calc.py"),
            ),
        )
        self.assertEqual(
            [entry.kind for entry in bracketed.timeline],
            [_PROMPT, ASSISTANT_MESSAGE, TOOL_CALL, TOOL_RESULT, _OUTPUT],
        )
        self.assertEqual(bracketed.timeline[0].content, _ASKED)
        self.assertEqual(bracketed.timeline[-1].content, _ANSWERED)

    def test_a_bracket_carries_no_step_fields(self) -> None:
        # The entry keeps the producing step's turn so the page can render the
        # per-turn usage strip at the boundary while walking the timeline.
        bracketed = run(
            user_input=_ASKED,
            steps=(step(TOOL_CALL, name=TOOL_BASH, tool_id=_TOOL_ID, turn=0),),
        )
        opening, call = bracketed.timeline
        self.assertEqual(
            (call.name, call.tool_id, call.turn), (TOOL_BASH, _TOOL_ID, 0),
        )
        self.assertEqual(
            (opening.name, opening.tool_id, opening.turn), ("", "", None),
        )

    def test_an_empty_field_yields_no_bracket(self) -> None:
        # A run that was never answered is its prompt alone rather than a
        # trailing blank entry.
        for fields, expected in (
            ({"steps": (step(TOOL_CALL),)}, [TOOL_CALL]),
            ({"user_input": _ASKED}, [_PROMPT]),
            ({"output": _ANSWERED}, [_OUTPUT]),
            ({}, []),
        ):
            with self.subTest(fields=sorted(fields)):
                timeline = run(**fields).timeline
                self.assertEqual([entry.kind for entry in timeline], expected)


class FixtureDetectionTest(unittest.TestCase):
    """The tells that mark a record the test suite left behind."""

    def test_each_tell_flags_a_synthetic_record(self) -> None:
        # Case and surrounding whitespace do not hide the sentinel prompt, and
        # a run whose only tool work is loading skills is a fixture too.
        for fields in (
            {"user_input": _FIXTURE_PROMPT},
            {"user_input": "  IGNORED "},
            {"session_id": "sess-dev"},
            {"steps": (step(TOOL_CALL, name=TOOL_SKILL, content=_SKILL_DEVELOP),)},
        ):
            with self.subTest(fields=sorted(fields)):
                self.assertTrue(run(**fields).is_fixture)

    def test_a_real_run_is_not_flagged(self) -> None:
        # A real prompt, a uuid session id, and a Skill call among real tool
        # work: no tell fires.
        real = run(
            user_input="please fix issue 7",
            session_id="0f9a3c2e-1b4d-4a77-9c12-abcdef012345",
            steps=(
                step(TOOL_CALL, name=TOOL_SKILL, content=_SKILL_DEVELOP),
                step(TOOL_CALL, name=TOOL_BASH, content="pytest"),
                step(TOOL_RESULT, tool_id=_TOOL_ID),
            ),
        )
        self.assertFalse(real.is_fixture)

    def test_a_stepless_run_is_not_skill_only(self) -> None:
        # "Every step is a Skill call" is vacuously true of no steps, so a
        # real run that recorded none would otherwise be hidden by the toggle.
        self.assertFalse(run(user_input="real", session_id="abc123").is_fixture)


class RunLabelTest(unittest.TestCase):
    """One name, split where the run pickers need it."""

    def test_the_detail_names_a_run_s_cohort(self) -> None:
        # The repository and issue are picked before it, so they are left out.
        reviewed = run(
            stage=_STAGE, agent_role=_ROLE, backend=_BACKEND, review_round=0,
        )
        self.assertEqual(
            reviewed.detail_label(),
            f"{_STAGE}/{_ROLE} · {_BACKEND} · round 0 · {reviewed.ts}",
        )

    def test_a_run_outside_a_review_omits_the_round(self) -> None:
        self.assertNotIn("round", run(stage=_STAGE).detail_label())

    def test_an_unrecorded_field_renders_as_a_dash(self) -> None:
        # An empty stage, role, or backend has to stay visible as a column of
        # the cohort rather than collapse the label into punctuation.
        bare = run()
        self.assertEqual(bare.detail_label(), f"—/— · — · {bare.ts}")

    def test_the_label_is_the_detail_behind_its_issue(self) -> None:
        labelled = run(stage=_STAGE, agent_role=_ROLE, backend=_BACKEND)
        self.assertEqual(
            labelled.label(),
            f"#{labelled.issue} {labelled.repo} · {labelled.detail_label()}",
        )


if __name__ == "__main__":
    unittest.main()
