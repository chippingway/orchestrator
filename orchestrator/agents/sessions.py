# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Claude final-message JSONL parsing, read against that CLI's own schema.

The parsers answer what the CLI said: what a run's last message was and which
terminal event carried it, named block type by block type as Claude emits them.
Which session the run belongs to is asked of every backend and asked
structurally, so it belongs to the `session_ids` owner rather than here. What
the text means for the provider behind the run is the `provider_failures`
owner's question, and the two published readers here -- the terminal result
event and the result string on one -- are what it reads the stream through, so
the events are walked in one place whichever question is being asked.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any


def _iter_claude_events(jsonl_output: str) -> Iterator[dict[str, Any]]:
    """Yield the JSON objects in Claude's mixed JSONL output.

    The CLI interleaves the stream with blank lines and human-readable
    diagnostics, and nothing guarantees a decoded line is a mapping, so every
    reader here would otherwise repeat the same three rejections.
    """
    for raw_line in jsonl_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event_payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event_payload, dict):
            yield event_payload


def _collect_claude_text_blocks(
    content_blocks: list[Any],
) -> str | None:
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


def claude_result_text(
    event_payload: dict[str, Any],
) -> str | None:
    """Return a terminal result string without filtering its subtype."""
    if event_payload.get("type") != "result":
        return None
    result_text = event_payload.get("result")
    return result_text if isinstance(result_text, str) else None


def _claude_assistant_text(
    event_payload: dict[str, Any],
) -> str | None:
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
) -> tuple[str | None, str | None]:
    """Keep the latest terminal and assistant message candidates."""
    last_result: str | None = None
    last_assistant_text: str | None = None
    for event_payload in events:
        result_text = claude_result_text(event_payload)
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


def claude_terminal_result_event(
    jsonl_output: str,
) -> dict[str, Any] | None:
    """Return the LAST event carrying a terminal result string, if any."""
    terminal_event: dict[str, Any] | None = None
    for event_payload in _iter_claude_events(jsonl_output):
        if claude_result_text(event_payload) is not None:
            terminal_event = event_payload
    return terminal_event
