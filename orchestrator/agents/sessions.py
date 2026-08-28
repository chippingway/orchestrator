# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Backend-agnostic session-id and Claude final-message JSONL parsing, and the
one verdict a run's own output can give about the provider behind it.

The parsers answer what the CLI said. `is_transient_provider_failure` answers
whether it said anything at all of its own: an `API Error: 529 Overloaded` is
the provider refusing to serve the turn, so the text that reaches the caller
is the refusal rather than the agent's words. Every stage that reads a final
message as the agent's own has to ask that first, which is why the classifier
lives beside the parsers instead of inside one stage.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional, Tuple

from orchestrator.agents import models as _agent_models

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_PRIORITY_KEYS = ("session_id", "conversation_id", "thread_id", "session", "id")

# The server-side refusals a retry is the whole recovery for, matched as a
# PREFIX of the normalized final message. Deliberately only the 5xx family and
# the overload the provider names in words: a 4xx is a request this account may
# not make (auth, permission, a payload the model refused) and retrying it
# changes nothing, and a 429 is quota, whose CLI-level phrasings the
# session-limit classifier already routes to "wait for the reset".
_TRANSIENT_PROVIDER_MESSAGE_MARKERS: Tuple[str, ...] = (
    "api error: 500",
    "api error: 502",
    "api error: 503",
    "api error: 504",
    "api error: 529",
    "api error: overloaded",
)


def _first_nested_uuid(payload_nodes: Iterator[Any]) -> Optional[str]:
    for payload_node in payload_nodes:
        found_uuid = _walk_for_uuid(payload_node)
        if found_uuid is not None:
            return found_uuid
    return None


def _walk_mapping_for_uuid(payload_node: dict[Any, Any]) -> Optional[str]:
    priority_values = (
        payload_node[key]
        for key in _PRIORITY_KEYS
        if key in payload_node
    )
    priority_match = _first_nested_uuid(priority_values)
    if priority_match is not None:
        return priority_match
    return _first_nested_uuid(iter(payload_node.values()))


def _walk_for_uuid(payload_node: Any) -> Optional[str]:
    if isinstance(payload_node, str):
        return payload_node if _UUID_RE.match(payload_node) else None
    if isinstance(payload_node, dict):
        return _walk_mapping_for_uuid(payload_node)
    if isinstance(payload_node, list):
        return _first_nested_uuid(iter(payload_node))
    return None


def parse_session_id(jsonl_output: str) -> Optional[str]:
    """Return the first UUID at a known key anywhere in JSONL events."""
    for raw_line in jsonl_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event_payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = _walk_for_uuid(event_payload)
        if session_id:
            return session_id
    return None


def _decode_claude_event(raw_line: str) -> Optional[dict[str, Any]]:
    """Decode one stream event, ignoring blank or diagnostic output."""
    line = raw_line.strip()
    if not line:
        return None
    try:
        event_payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    return event_payload if isinstance(event_payload, dict) else None


def _iter_claude_events(jsonl_output: str) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from Claude's mixed JSONL output."""
    for raw_line in jsonl_output.splitlines():
        event_payload = _decode_claude_event(raw_line)
        if event_payload is not None:
            yield event_payload


def _collect_claude_text_blocks(
    content_blocks: list[Any],
) -> Optional[str]:
    """Join valid text blocks from one assistant message."""
    text_blocks: list[str] = []
    for content_block in content_blocks:
        if not isinstance(content_block, dict):
            continue
        if content_block.get("type") != "text":
            continue
        block_text = content_block.get("text")
        if isinstance(block_text, str):
            text_blocks.append(block_text)
    return "".join(text_blocks) if text_blocks else None


def _claude_result_text(
    event_payload: dict[str, Any],
) -> Optional[str]:
    """Return a terminal result string without filtering its subtype."""
    if event_payload.get("type") != "result":
        return None
    result_text = event_payload.get("result")
    return result_text if isinstance(result_text, str) else None


def _claude_assistant_text(
    event_payload: dict[str, Any],
) -> Optional[str]:
    """Return text from a supported assistant or message event."""
    if event_payload.get("type") not in ("assistant", "message"):
        return None
    nested_message = event_payload.get("message")
    message_payload = (
        nested_message if isinstance(nested_message, dict) else event_payload
    )
    message_content = message_payload.get("content")
    if isinstance(message_content, list):
        return _collect_claude_text_blocks(message_content)
    return message_content if isinstance(message_content, str) else None


def _collect_claude_message_candidates(
    events: Iterator[dict[str, Any]],
) -> tuple[Optional[str], Optional[str]]:
    """Keep the latest terminal and assistant message candidates."""
    last_result: Optional[str] = None
    last_assistant_text: Optional[str] = None
    for event_payload in events:
        result_text = _claude_result_text(event_payload)
        if result_text is not None:
            last_result = result_text
        assistant_text = _claude_assistant_text(event_payload)
        if assistant_text is not None:
            last_assistant_text = assistant_text
    return last_result, last_assistant_text


def claude_last_message(
    jsonl_output: str,
    *,
    allow_assistant_fallback: bool = True,
) -> str:
    """Prefer terminal output and optionally fall back to assistant text."""
    candidates = _collect_claude_message_candidates(
        _iter_claude_events(jsonl_output),
    )
    last_result, last_assistant_text = candidates
    if last_result is not None:
        return last_result
    if allow_assistant_fallback:
        return last_assistant_text or ""
    return ""


def _has_transient_provider_marker(message: Any) -> bool:
    """True iff `message` OPENS with a known transient provider refusal."""
    if not isinstance(message, str):
        return False
    return message.strip().lower().startswith(_TRANSIENT_PROVIDER_MESSAGE_MARKERS)


def _claude_terminal_result_event(
    jsonl_output: str,
) -> Optional[dict[str, Any]]:
    """Return the LAST event carrying a terminal result string, if any."""
    terminal_event: Optional[dict[str, Any]] = None
    for event_payload in _iter_claude_events(jsonl_output):
        if _claude_result_text(event_payload) is not None:
            terminal_event = event_payload
    return terminal_event


def _structured_provider_verdict(jsonl_output: str) -> Optional[bool]:
    """Return the backend's OWN verdict on a run, or None when it gave none.

    Claude's terminal result event carries `is_error`, which is the only
    signal that separates a provider refusal from an agent that merely wrote
    about one: a successful turn quoting `API Error: 529 Overloaded` back at
    the operator is flagged `is_error: false` and must stay a real answer. A
    stream with no result event, or an older CLI whose result event omits the
    flag, said nothing on the question -- None sends the caller to the
    exit-code fallback rather than letting a missing key read as "healthy".
    """
    terminal_event = _claude_terminal_result_event(jsonl_output)
    if terminal_event is None or "is_error" not in terminal_event:
        return None
    if terminal_event["is_error"] is not True:
        return False
    return _has_transient_provider_marker(_claude_result_text(terminal_event))


def is_transient_provider_failure(
    agent_result: _agent_models.AgentResult,
) -> bool:
    """True iff this run ended in a known transient provider refusal.

    The CLI hands a `529 Overloaded` back through the same non-empty final
    message a real agent question arrives on, so a stage that reads that field
    as the agent's words would post a server outage as "agent needs your
    input" and then resume the same doomed session on the reply. Callers ask
    this first and route a True through their retryable session-failure park
    instead.

    Structured backend information wins where there is any: the terminal
    result event's `is_error` flag settles whether the text is the run's
    outcome or its subject. Without it -- a backend that emits no such event,
    or output nothing parsed -- the marker is only honored beside a NON-ZERO
    exit, so a clean run is never reclassified on its prose alone.
    """
    structured_verdict = _structured_provider_verdict(agent_result.stdout or "")
    if structured_verdict is not None:
        return structured_verdict
    if agent_result.exit_code == 0:
        return False
    return _has_transient_provider_marker(agent_result.last_message)
