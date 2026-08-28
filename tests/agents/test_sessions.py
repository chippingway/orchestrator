# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Session-id, Claude final-message, and provider-failure parsing owner tests."""

from __future__ import annotations

import json
import unittest

from orchestrator.agents import sessions as _sessions
from orchestrator.agents.models import AgentResult
from tests.agents import agent_test_values as _agent_cases


class ParseSessionIdTest(unittest.TestCase):
    def test_codex_jsonl_session_id(self) -> None:
        # Codex's --json output has session_id at varied paths; the walker
        # picks any UUID at a known key, anywhere in the tree.
        line = json.dumps(
            {
                _agent_cases._TYPE_FIELD: "task_started",
                _agent_cases._SESSION_ID_FIELD: "11111111-2222-3333-4444-555555555555",
            }
        )
        self.assertEqual(
            _sessions.parse_session_id(line),
            "11111111-2222-3333-4444-555555555555",
        )

    def test_claude_stream_json_session_id(self) -> None:
        # Claude's stream-json puts session_id on the system/init event and
        # on most subsequent events; a top-level UUID at session_id is the
        # documented surface.
        events = [
            json.dumps(
                {
                    _agent_cases._TYPE_FIELD: "system",
                    "subtype": "init",
                    _agent_cases._SESSION_ID_FIELD: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "tools": [],
                }
            ),
            json.dumps(
                {
                    _agent_cases._TYPE_FIELD: _agent_cases._ASSISTANT_EVENT,
                    _agent_cases._SESSION_ID_FIELD: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    _agent_cases._MESSAGE_FIELD: {
                        "role": _agent_cases._ASSISTANT_EVENT,
                        _agent_cases._CONTENT_FIELD: [],
                    },
                }
            ),
        ]
        self.assertEqual(
            _sessions.parse_session_id("\n".join(events)),
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )

    def test_nested_uuid_at_known_key(self) -> None:
        # The walker recurses through nested mappings and lists, so a UUID at a
        # priority key buried under non-priority keys is still discovered.
        payload = json.dumps(
            {
                _agent_cases._TYPE_FIELD: _agent_cases._ASSISTANT_EVENT,
                _agent_cases._MESSAGE_FIELD: {
                    "metadata": [
                        {"conversation_id": "abcdef01-2345-6789-abcd-ef0123456789"},
                    ],
                },
            }
        )
        self.assertEqual(
            _sessions.parse_session_id(payload),
            "abcdef01-2345-6789-abcd-ef0123456789",
        )

    def test_no_uuid_returns_none(self) -> None:
        payload = json.dumps({_agent_cases._TYPE_FIELD: "banner", "msg": "hello"})
        self.assertIsNone(_sessions.parse_session_id(payload))

    def test_skips_unparseable_lines(self) -> None:
        event = json.dumps({_agent_cases._SESSION_ID_FIELD: "12341234-1234-1234-1234-123412341234"})
        out = f"not-json\n{event}"
        self.assertEqual(
            _sessions.parse_session_id(out),
            "12341234-1234-1234-1234-123412341234",
        )


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


def _claude_result_event(result_text: str, **result_fields) -> str:
    """One terminal result frame, optionally carrying the `is_error` flag."""
    return json.dumps(
        {
            _agent_cases._TYPE_FIELD: _agent_cases._RESULT_FIELD,
            _agent_cases._RESULT_FIELD: result_text,
            **result_fields,
        }
    )


def _agent_result(
    last_message: str = "", *, exit_code: int = 0, stdout: str = "",
) -> AgentResult:
    return AgentResult(
        session_id=None,
        last_message=last_message,
        exit_code=exit_code,
        timed_out=False,
        stdout=stdout,
        stderr="",
    )


# `(result text, is_error, exit code, transient?)`.
_STRUCTURED_VERDICT_CASES = (
    (_agent_cases._OVERLOADED_RESULT, True, 0, True),
    (_agent_cases._OVERLOADED_RESULT, False, 1, False),
    (_agent_cases._OVERLOADED_MENTION, False, 0, False),
    # Flagged, but not a refusal a retry on a fresh session recovers from.
    ("Error: No such file or directory (os error 2)", True, 1, False),
)


class TransientProviderFailureTest(unittest.TestCase):
    """A provider refusal arrives through the same final-message field an
    agent's own answer does, so every stage that reads that field as the
    agent's words asks this first. It must recognize the observed
    `API Error: 529 Overloaded` and its 5xx siblings, refuse to reclassify a
    run that merely wrote about one, and leave every other failure alone.
    """

    def test_structured_flag_outranks_exit_code(self) -> None:
        # `is_error` is the backend's own verdict on whether the result text is
        # the run's outcome or its subject, so it outranks the exit code in
        # BOTH directions: a flagged refusal is transient even on a clean exit,
        # and a successful answer quoting the refusal stays an answer even on a
        # dirty one.
        for result_text, is_error, exit_code, expected in _STRUCTURED_VERDICT_CASES:
            with self.subTest(result_text=result_text, is_error=is_error):
                flagged = _agent_result(
                    result_text,
                    exit_code=exit_code,
                    stdout=_claude_result_event(
                        result_text, **{_agent_cases._IS_ERROR_FIELD: is_error},
                    ),
                )
                self.assertEqual(
                    _sessions.is_transient_provider_failure(flagged),
                    expected,
                )

    def test_marker_needs_nonzero_exit_unflagged(self) -> None:
        # No structured verdict at all (a backend that emits none) and a result
        # event from a CLI that omits the flag both fall back to the exit code,
        # which is what keeps a clean run from being reclassified on its prose.
        for stdout in ("", _claude_result_event(_agent_cases._OVERLOADED_RESULT)):
            with self.subTest(has_result_event=bool(stdout)):
                failed = _agent_result(
                    _agent_cases._OVERLOADED_RESULT, exit_code=1, stdout=stdout,
                )
                self.assertTrue(_sessions.is_transient_provider_failure(failed))
                succeeded = _agent_result(
                    _agent_cases._OVERLOADED_RESULT, exit_code=0, stdout=stdout,
                )
                self.assertFalse(_sessions.is_transient_provider_failure(succeeded))

    def test_marker_is_prefix_over_server_errors(self) -> None:
        # Matched as a PREFIX so a dev writing about the outage mid-answer is
        # left alone, and only over the server-side family: a 4xx is a request
        # this account may not make and a 429 is quota, neither of which a
        # retry on a fresh session recovers.
        transient = (
            _agent_cases._OVERLOADED_RESULT,
            "API Error: 500 Internal server error",
            "API Error: 502 Bad Gateway",
            "API Error: 503 Service Unavailable",
            "API Error: 504 Gateway Timeout",
            "  api error: overloaded_error",
        )
        for last_message in transient:
            with self.subTest(last_message=last_message):
                self.assertTrue(
                    _sessions.is_transient_provider_failure(
                        _agent_result(last_message, exit_code=1),
                    ),
                )
        left_alone = (
            "",
            _agent_cases._OVERLOADED_MENTION,
            "Should I prefer ruff or black for this?",
            "API Error: 400 Bad Request",
            "API Error: 401 Unauthorized",
            "API Error: 429 Too Many Requests",
        )
        for last_message in left_alone:
            with self.subTest(last_message=last_message):
                self.assertFalse(
                    _sessions.is_transient_provider_failure(
                        _agent_result(last_message, exit_code=1),
                    ),
                )
