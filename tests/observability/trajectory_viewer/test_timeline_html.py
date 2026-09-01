# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How one timeline entry is titled, and which entry a usage strip sits above."""
from __future__ import annotations

import unittest
from typing import Any

from orchestrator.observability.trajectory_viewer import (
    constants,
    models,
    runs,
    timeline_html,
)
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    ASSISTANT_MESSAGE,
    TOOL_BASH,
    TOOL_CALL,
    TOOL_EDIT,
    TOOL_RESULT,
    run,
    step,
)

_T1 = "t1"

_UNKNOWN_KIND = "weird"

_FIRST_TURN = 0

_SECOND_TURN = 1


def _entry(kind: str, **fields: Any) -> models.TimelineEntry:
    return models.TimelineEntry(kind=kind, **fields)


def _run_with_turns() -> runs.TrajectoryRun:
    """A run whose second turn opens after a tool call and its result."""
    return run(
        steps=(
            step(ASSISTANT_MESSAGE, content="a", turn=_FIRST_TURN),
            step(TOOL_CALL, name=TOOL_EDIT, tool_id=_T1, turn=_FIRST_TURN),
            step(TOOL_RESULT, tool_id=_T1),
            step(ASSISTANT_MESSAGE, content="b", turn=_SECOND_TURN),
        ),
        turns=(
            models.TurnUsageView(turn=_FIRST_TURN),
            models.TurnUsageView(turn=_SECOND_TURN),
        ),
    )


class TimelineEntryKindHtmlTest(unittest.TestCase):
    """Each kind gets the badge class and wording the page names it by."""

    def test_each_known_kind_reads_as_its_badge(self) -> None:
        for kind, badge_class, badge_text in (
            (constants.TIMELINE_PROMPT, "prompt", "prompt"),
            (constants.TIMELINE_OUTPUT, "output", "final output"),
            (TOOL_CALL, "call", "tool call"),
            (TOOL_RESULT, "result", "tool result"),
            (ASSISTANT_MESSAGE, "assistant", "assistant"),
            ("user_message", "user", "user turn"),
        ):
            with self.subTest(kind=kind):
                rendered = timeline_html.timeline_entry_html(_entry(kind), 0)
                self.assertIn(f"orch-traj-badge {badge_class}", rendered)
                self.assertIn(f">{badge_text}</span>", rendered)

    def test_unknown_kind_falls_through(self) -> None:
        # A record from a newer sink still renders: the kind is printed as
        # written rather than dropping the step out of the timeline.
        rendered = timeline_html.timeline_entry_html(_entry(_UNKNOWN_KIND), 0)
        self.assertIn("orch-traj-badge result", rendered)
        self.assertIn(f">{_UNKNOWN_KIND}</span>", rendered)

    def test_tool_call_carries_its_name_and_id(self) -> None:
        rendered = timeline_html.timeline_entry_html(
            _entry(TOOL_CALL, name=TOOL_BASH, tool_id=_T1), 1,
        )
        self.assertIn(f">{TOOL_BASH}</span>", rendered)
        self.assertIn(_T1, rendered)

    def test_step_number_reads_one_based(self) -> None:
        # The index is the caller's loop counter; an operator counts from one.
        rendered = timeline_html.timeline_entry_html(_entry(TOOL_RESULT), 4)
        self.assertIn(">5</span>", rendered)

    def test_name_escaped(self) -> None:
        rendered = timeline_html.timeline_entry_html(
            _entry(TOOL_CALL, name="<x>"), 0,
        )
        self.assertIn("&lt;x&gt;", rendered)
        self.assertNotIn("<x></span>", rendered)


class TimelineUsageBoundaryTest(unittest.TestCase):
    """A strip is drawn once per assistant turn, at the entry that opens it."""

    def test_strip_only_at_first_entry_of_each_turn(self) -> None:
        strips = [strip for strip, _ in timeline_html.timeline_with_usage(
            _run_with_turns(),
        )]
        self.assertEqual(len(strips), 4)
        self.assertEqual(strips[0].turn, _FIRST_TURN)
        # The same turn's tool call and the turn-input result carry no strip.
        self.assertIsNone(strips[1])
        self.assertIsNone(strips[2])
        self.assertEqual(strips[3].turn, _SECOND_TURN)

    def test_no_strip_on_turn_none_entries(self) -> None:
        for strip, entry in timeline_html.timeline_with_usage(_run_with_turns()):
            if entry.turn is None:
                self.assertIsNone(strip)

    def test_pre_usage_run_pairs_entries_with_none(self) -> None:
        paired = timeline_html.timeline_with_usage(run(steps=(
            step(TOOL_CALL, name=TOOL_BASH),
            step(TOOL_RESULT, tool_id="t"),
        )))
        self.assertTrue(paired)
        self.assertTrue(all(strip is None for strip, _ in paired))


if __name__ == "__main__":
    unittest.main()
