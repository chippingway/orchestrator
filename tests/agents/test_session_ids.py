# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Session-id walker owner tests."""

from __future__ import annotations

import json
import unittest

from orchestrator.agents import session_ids as _session_ids
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
            _session_ids.parse_session_id(line),
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
            _session_ids.parse_session_id("\n".join(events)),
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
            _session_ids.parse_session_id(payload),
            "abcdef01-2345-6789-abcd-ef0123456789",
        )

    def test_no_uuid_returns_none(self) -> None:
        payload = json.dumps({_agent_cases._TYPE_FIELD: "banner", "msg": "hello"})
        self.assertIsNone(_session_ids.parse_session_id(payload))

    def test_skips_unparseable_lines(self) -> None:
        event = json.dumps({_agent_cases._SESSION_ID_FIELD: "12341234-1234-1234-1234-123412341234"})
        out = f"not-json\n{event}"
        self.assertEqual(
            _session_ids.parse_session_id(out),
            "12341234-1234-1234-1234-123412341234",
        )
