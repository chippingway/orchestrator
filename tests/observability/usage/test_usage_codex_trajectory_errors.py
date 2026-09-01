# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Codex malformed and partial trajectory tests."""

import json
import unittest
from types import MappingProxyType

from orchestrator.observability.usage import trajectory_models as _records
from orchestrator.observability.usage import skills as _skills
from orchestrator.observability.usage import trajectory as _trajectory
from tests.observability.usage import usage_test_values as _usage_cases
from tests.observability.usage import usage_jsonl_helpers as _jsonl
from tests.observability.usage import usage_codex_events as _codex


class CodexTrajectoryErrorTest(unittest.TestCase):
    """``_trajectory.parse_codex_trajectory`` over synthetic ``codex exec --json`` runs.

    Every operational item codex reports is one ordered pair -- an invocation
    and, only when a frame actually carried one, an outcome -- deduped by the
    shared ``item.id`` across the started/updated/completed frames; each
    ``agent_message`` is one ``assistant_message`` text turn (its ``text``),
    captured in stream order. The last ``agent_message`` ``text`` is also the
    final output; ``tools`` / ``system_prompt`` stay empty (no confirmed codex
    frame exposes them).
    """

    def test_null_aggregate_still_emits_result(self) -> None:
        # A completed command whose ``aggregated_output`` is present but null
        # still emits a tool_result step (content None): on the frame that
        # completes a command the recorded-output decision is membership, not
        # truthiness, so a null result is kept.
        stdout = _jsonl.jsonl(
            _codex.command(
                _usage_cases.ITEM_ONE_ID,
                "/bin/bash -lc 'true'",
                status=_usage_cases.COMPLETED_STATUS,
                aggregated_output=None,
            ),
        )
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(
            [step.kind for step in trajectory.steps],
            [_usage_cases.TOOL_CALL_STEP, _usage_cases.TOOL_RESULT_STEP],
        )
        self.assertIsNone(trajectory.steps[1].content)

    def test_missing_fields_yield_empty_sections(self) -> None:
        stdout = _jsonl.jsonl(
            {_usage_cases.TYPE_FIELD: _usage_cases.THREAD_STARTED_EVENT},
            {
                _usage_cases.TYPE_FIELD: _usage_cases.TURN_COMPLETED_EVENT,
                _usage_cases.USAGE_FIELD: {_usage_cases.INPUT_TOKENS_FIELD: 1},
            },
        )
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(trajectory.steps, ())
        self.assertIsNone(trajectory.final_output)
        self.assertEqual(trajectory.tools, ())
        self.assertEqual(trajectory.skills, _skills.SkillTriggers())

    def test_malformed_lines_are_skipped(self) -> None:
        good = json.dumps(
            _codex.command(
                _usage_cases.ITEM_ONE_ID,
                _usage_cases.SHELL_LIST_COMMAND,
                status=_usage_cases.COMPLETED_STATUS,
                aggregated_output=_usage_cases.COMMAND_OUTPUT,
            )
        )
        stdout = _jsonl.stdout_lines(
            "codex starting...",
            '{"truncated":',
            good,
            "trailing-noise",
        )
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(
            [step.kind for step in trajectory.steps], [_usage_cases.TOOL_CALL_STEP, _usage_cases.TOOL_RESULT_STEP]
        )

    def test_has_no_per_turn_usage(self) -> None:
        # Codex usage frames are cumulative, not per-turn, so the per-turn
        # section stays empty and no step is stamped with a turn index -- the
        # run-level summary is codex's only usage surface (mirrors how tools /
        # skills_available stay best-effort-empty for codex).
        stdout = _jsonl.jsonl(
            _codex.command(
                _usage_cases.ITEM_ONE_ID,
                _usage_cases.SHELL_LIST_COMMAND,
                status=_usage_cases.COMPLETED_STATUS,
                aggregated_output=_usage_cases.COMMAND_OUTPUT,
            ),
            _codex.agent_message(_usage_cases.AGENT_MESSAGE_ID, _usage_cases.FINAL_OUTPUT),
            {
                _usage_cases.TYPE_FIELD: _usage_cases.TURN_COMPLETED_EVENT,
                _usage_cases.USAGE_FIELD: {
                    _usage_cases.INPUT_TOKENS_FIELD: 10,
                    _usage_cases.OUTPUT_TOKENS_FIELD: 5,
                },
            },
        )
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        self.assertEqual(trajectory.turns, ())
        self.assertTrue(trajectory.steps)
        self.assertTrue(all(step.turn is None for step in trajectory.steps))

    def test_empty_stdout(self) -> None:
        self.assertEqual(_trajectory.parse_codex_trajectory(""), _records.AgentTrajectory(backend=_usage_cases.CODEX))


_MCP_SERVER = "docsServer"
_MCP_TOOL = "fetch_doc"
_ERROR_ITEM = "error"


def _mcp_arguments() -> dict:
    """The arguments frame the MCP cases invoke their tool with."""
    return {"url": "https://example.invalid/x"}


# One frame per unclaimed / excluded item type, paired with the steps it is
# expected to leave behind.
_UNCLAIMED_CASES = MappingProxyType({
    "status reported": (
        {
            _usage_cases.IDENTIFIER_FIELD: _usage_cases.ITEM_ONE_ID,
            _usage_cases.TYPE_FIELD: "collab_tool_call",
            _usage_cases.STATUS_FIELD: _usage_cases.FAILED_STATUS,
        },
        [(
            _usage_cases.UNSUPPORTED_ITEM_STEP,
            "collab_tool_call",
            _usage_cases.FAILED_STATUS,
        )],
    ),
    "no status field": (
        {
            _usage_cases.IDENTIFIER_FIELD: _usage_cases.ITEM_ONE_ID,
            _usage_cases.TYPE_FIELD: _ERROR_ITEM,
            "message": "model metadata not found",
        },
        [(_usage_cases.UNSUPPORTED_ITEM_STEP, _ERROR_ITEM, None)],
    ),
    "reasoning excluded": (
        {
            _usage_cases.IDENTIFIER_FIELD: _usage_cases.ITEM_ONE_ID,
            _usage_cases.TYPE_FIELD: "reasoning",
            _usage_cases.TEXT_FIELD: "**Thinking**",
        },
        [],
    ),
    "type-less item": (
        {
            _usage_cases.IDENTIFIER_FIELD: _usage_cases.ITEM_ONE_ID,
            _usage_cases.STATUS_FIELD: _usage_cases.COMPLETED_STATUS,
        },
        [],
    ),
})


class CodexUnclaimedItemTest(unittest.TestCase):
    """What an item type the parser does not normalize leaves behind.

    An unclaimed operational item becomes a placeholder naming the type, the
    id, and the status it reported, so a surface a later codex release adds is
    read off the timeline rather than missed. Reasoning is the exclusion the
    placeholder does not apply to: its text is hidden model content, and one
    placeholder per reasoning item would be noise.
    """

    def test_unclaimed_items_become_placeholders(self) -> None:
        for name, (frame, expected) in _UNCLAIMED_CASES.items():
            with self.subTest(case=name):
                self.assertEqual(self._steps_of(frame), expected)

    def test_mcp_error_payload_completes_the_pair(self) -> None:
        # A tool call the server rejected fills ``error`` and leaves ``result``
        # null, so the error payload is the outcome the pair is completed with
        # rather than a call left with nothing under it.
        frame = {
            _usage_cases.IDENTIFIER_FIELD: _usage_cases.ITEM_ONE_ID,
            _usage_cases.TYPE_FIELD: _usage_cases.MCP_TOOL_CALL_ITEM,
            "server": _MCP_SERVER,
            "tool": _MCP_TOOL,
            "arguments": _mcp_arguments(),
            "result": None,
            "error": {"message": "tool not found"},
            _usage_cases.STATUS_FIELD: _usage_cases.FAILED_STATUS,
        }
        self.assertEqual(
            self._steps_of(frame),
            [
                (
                    _usage_cases.TOOL_CALL_STEP,
                    f"{_MCP_SERVER}.{_MCP_TOOL}",
                    _mcp_arguments(),
                ),
                (
                    _usage_cases.TOOL_RESULT_STEP,
                    "",
                    {"message": "tool not found"},
                ),
            ],
        )

    def test_unnamed_mcp_call_falls_back_to_type(self) -> None:
        # Neither half of the name arrived, so the call still names what was
        # invoked rather than carrying an empty tool name -- and the call the
        # stream never completed gets no result invented for it.
        frame = {
            _usage_cases.IDENTIFIER_FIELD: _usage_cases.ITEM_ONE_ID,
            _usage_cases.TYPE_FIELD: _usage_cases.MCP_TOOL_CALL_ITEM,
            "arguments": _mcp_arguments(),
            "result": None,
            "error": None,
            _usage_cases.STATUS_FIELD: _usage_cases.IN_PROGRESS_STATUS,
        }
        self.assertEqual(
            self._steps_of(frame),
            [(
                _usage_cases.TOOL_CALL_STEP,
                _usage_cases.MCP_TOOL_CALL_ITEM,
                _mcp_arguments(),
            )],
        )

    def _steps_of(self, frame: dict) -> list:
        stdout = _jsonl.jsonl({
            _usage_cases.TYPE_FIELD: _usage_cases.ITEM_COMPLETED_EVENT,
            _usage_cases.ITEM_FIELD: frame,
        })
        trajectory = _trajectory.parse_codex_trajectory(stdout)
        return [
            (step.kind, step.name, step.content)
            for step in trajectory.steps
        ]
