# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory timeline-entry HTML tests."""

import unittest


from orchestrator import trajectory_reader as tr


_TOOL_CALL = "tool_call"


_TOOL_RESULT = "tool_result"


_TOOL_BASH = "Bash"


_T1 = "t1"


def _td():
    from orchestrator import trajectory_dashboard as td
    return td


class TimelineEntryKindHtmlTest(unittest.TestCase):
    def test_prompt_bracket_badge(self) -> None:
        entry = tr.TimelineEntry(kind=tr.TIMELINE_PROMPT, content="do x")
        html = _td()._timeline_entry_html(entry, 0)
        self.assertIn("orch-traj-badge prompt", html)
        self.assertIn(">prompt</span>", html)
        # 0-based index renders 1-based for humans.
        self.assertIn(">1</span>", html)

    def test_output_bracket_badge(self) -> None:
        entry = tr.TimelineEntry(kind=tr.TIMELINE_OUTPUT, content="done")
        html = _td()._timeline_entry_html(entry, 4)
        self.assertIn("orch-traj-badge output", html)
        self.assertIn(">final output</span>", html)
        self.assertIn(">5</span>", html)

    def test_tool_call_badge_name_and_id(self) -> None:
        entry = tr.TimelineEntry(kind=_TOOL_CALL, name=_TOOL_BASH, tool_id=_T1)
        html = _td()._timeline_entry_html(entry, 1)
        self.assertIn("orch-traj-badge call", html)
        self.assertIn(">tool call</span>", html)
        self.assertIn(">Bash</span>", html)
        self.assertIn(_T1, html)

    def test_tool_result_badge(self) -> None:
        entry = tr.TimelineEntry(kind=_TOOL_RESULT, tool_id=_T1)
        html = _td()._timeline_entry_html(entry, 2)
        self.assertIn("orch-traj-badge result", html)
        self.assertIn(">tool result</span>", html)

    def test_assistant_turn_badge(self) -> None:
        entry = tr.TimelineEntry(kind="assistant_message", content="hi")
        html = _td()._timeline_entry_html(entry, 0)
        self.assertIn("orch-traj-badge assistant", html)
        self.assertIn(">assistant</span>", html)

    def test_user_turn_badge(self) -> None:
        entry = tr.TimelineEntry(kind="user_message", content="more")
        html = _td()._timeline_entry_html(entry, 0)
        self.assertIn("orch-traj-badge user", html)
        self.assertIn(">user turn</span>", html)

    def test_unknown_kind_falls_through(self) -> None:
        entry = tr.TimelineEntry(kind="weird")
        html = _td()._timeline_entry_html(entry, 0)
        self.assertIn("orch-traj-badge result", html)
        self.assertIn(">weird</span>", html)


class TimelineEntryEscapingHtmlTest(unittest.TestCase):
    def test_name_escaped(self) -> None:
        entry = tr.TimelineEntry(kind=_TOOL_CALL, name="<x>")
        html = _td()._timeline_entry_html(entry, 0)
        self.assertIn("&lt;x&gt;", html)
        self.assertNotIn("<x></span>", html)
