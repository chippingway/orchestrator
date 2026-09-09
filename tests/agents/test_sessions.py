# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Claude final-message parsing owner tests."""

from __future__ import annotations

import json
import unittest

from orchestrator.agents import sessions as _sessions
from tests.agents import agent_test_values as _agent_cases


class ClaudeLastMessageTest(unittest.TestCase):
    def test_prefers_terminal_result_event(self) -> None:
        # The terminal `result` wins even when an assistant chunk streams after
        # it, so a last-assistant-text parser would return the wrong message.
        events = [
            json.dumps(
                {
                    _agent_cases._TYPE_FIELD: _agent_cases._RESULT_FIELD,
                    "subtype": "success",
                    _agent_cases._RESULT_FIELD: "final answer",
                }
            ),
            json.dumps(
                {
                    _agent_cases._TYPE_FIELD: _agent_cases._ASSISTANT_EVENT,
                    _agent_cases._MESSAGE_FIELD: {
                        _agent_cases._CONTENT_FIELD: [
                            {
                                _agent_cases._TYPE_FIELD: _agent_cases._TEXT_FIELD,
                                _agent_cases._TEXT_FIELD: "trailing chatter",
                            }
                        ],
                    },
                }
            ),
        ]
        self.assertEqual(_sessions.claude_last_message("\n".join(events)), "final answer")

    def test_falls_back_to_supported_message_shapes(self) -> None:
        cases = (
            (
                [
                    {
                        _agent_cases._TYPE_FIELD: _agent_cases._ASSISTANT_EVENT,
                        _agent_cases._MESSAGE_FIELD: {
                            _agent_cases._CONTENT_FIELD: [
                                {
                                    _agent_cases._TYPE_FIELD: _agent_cases._TEXT_FIELD,
                                    _agent_cases._TEXT_FIELD: "hello ",
                                },
                                {_agent_cases._TYPE_FIELD: _agent_cases._TEXT_FIELD, _agent_cases._TEXT_FIELD: "world"},
                            ],
                        },
                    }
                ],
                "hello world",
            ),
            (
                [
                    {
                        _agent_cases._TYPE_FIELD: _agent_cases._MESSAGE_FIELD,
                        _agent_cases._CONTENT_FIELD: "direct message",
                    }
                ],
                "direct message",
            ),
        )
        for event_payloads, expected in cases:
            with self.subTest(expected=expected):
                events = [json.dumps(payload) for payload in event_payloads]
                self.assertEqual(
                    _sessions.claude_last_message("\n".join(events)),
                    expected,
                )

    def test_ignores_diagnostics_and_bad_blocks(self) -> None:
        events = [
            "diagnostic text outside the JSON stream",
            json.dumps(["not", "an", "event"]),
            json.dumps({_agent_cases._TYPE_FIELD: "system", _agent_cases._CONTENT_FIELD: "not an answer"}),
            json.dumps(
                {
                    _agent_cases._TYPE_FIELD: _agent_cases._ASSISTANT_EVENT,
                    _agent_cases._MESSAGE_FIELD: {
                        _agent_cases._CONTENT_FIELD: [
                            {_agent_cases._TYPE_FIELD: "tool_use", _agent_cases._TEXT_FIELD: "ignored tool"},
                            {_agent_cases._TYPE_FIELD: _agent_cases._TEXT_FIELD, _agent_cases._TEXT_FIELD: 7},
                            "invalid block",
                            {
                                _agent_cases._TYPE_FIELD: _agent_cases._TEXT_FIELD,
                                _agent_cases._TEXT_FIELD: "kept answer",
                            },
                        ],
                    },
                }
            ),
        ]
        self.assertEqual(_sessions.claude_last_message("\n".join(events)), "kept answer")

    def test_keeps_last_string_result_for_error_event(self) -> None:
        events = [
            json.dumps(
                {_agent_cases._TYPE_FIELD: _agent_cases._RESULT_FIELD, _agent_cases._RESULT_FIELD: "earlier result"}
            ),
            json.dumps(
                {
                    _agent_cases._TYPE_FIELD: _agent_cases._RESULT_FIELD,
                    "subtype": "error_during_execution",
                    "is_error": True,
                    _agent_cases._RESULT_FIELD: "error details",
                }
            ),
            json.dumps(
                {_agent_cases._TYPE_FIELD: _agent_cases._RESULT_FIELD, _agent_cases._RESULT_FIELD: {"invalid": "shape"}}
            ),
        ]
        self.assertEqual(_sessions.claude_last_message("\n".join(events)), "error details")

    def test_empty_without_known_events(self) -> None:
        self.assertEqual(_sessions.claude_last_message(""), "")
        self.assertEqual(
            _sessions.claude_last_message('{"type":"system","subtype":"init"}'),
            "",
        )

    def test_fallback_gate_suppresses_partial_chunks(self) -> None:
        # With the fallback disabled, a transcript carrying only assistant
        # chunks yields ""; a terminal result event is still honored.
        self.assertEqual(
            _sessions.claude_last_message(
                _agent_cases._PARTIAL_CLAUDE_OUTPUT,
                allow_assistant_fallback=False,
            ),
            "",
        )
        result_frame = json.dumps(
            {_agent_cases._TYPE_FIELD: _agent_cases._RESULT_FIELD, _agent_cases._RESULT_FIELD: "final"}
        )
        with_result = f"{_agent_cases._PARTIAL_CLAUDE_OUTPUT}\n{result_frame}"
        self.assertEqual(
            _sessions.claude_last_message(with_result, allow_assistant_fallback=False),
            "final",
        )


class ClaudeTerminalResultEventTest(unittest.TestCase):
    """The whole terminal event, so a caller can read the fields beside its text.

    `claude_last_message` hands back the string alone, which is enough for a
    stage quoting the agent but not for the verdict owner: `is_error` sits on
    the same event and decides whether that string is the run's outcome or its
    subject. The event returned is the LAST one carrying a string result, the
    same one the final message is taken from.
    """

    def test_last_result_event_is_returned_whole(self) -> None:
        flagged_event = {
            _agent_cases._TYPE_FIELD: _agent_cases._RESULT_FIELD,
            _agent_cases._IS_ERROR_FIELD: True,
            _agent_cases._RESULT_FIELD: "error details",
        }
        events = [
            json.dumps(
                {_agent_cases._TYPE_FIELD: _agent_cases._RESULT_FIELD, _agent_cases._RESULT_FIELD: "earlier result"}
            ),
            json.dumps(flagged_event),
        ]
        self.assertEqual(
            _sessions.claude_terminal_result_event("\n".join(events)),
            flagged_event,
        )

    def test_none_without_a_string_result_event(self) -> None:
        for jsonl_output in ("", _agent_cases._PARTIAL_CLAUDE_OUTPUT):
            with self.subTest(has_events=bool(jsonl_output)):
                self.assertIsNone(_sessions.claude_terminal_result_event(jsonl_output))
