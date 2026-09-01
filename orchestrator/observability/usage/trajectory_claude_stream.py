# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Reconstruct the ordered Claude trajectory stream."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from orchestrator.observability.usage import (
    protocol,
    skills_claude,
    trajectory_claude_blocks,
)
from orchestrator.observability.usage.trajectory_models import TrajectoryStep


def offered_tools(events: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    return skills_claude.ordered_unique_names(
        skills_claude.claude_init_field(events, "tools"),
    )


def final_output(events: Iterable[dict[str, Any]]) -> str | None:
    final_text: str | None = None
    for event in events:
        if event.get(protocol.TYPE) != protocol.RESULT_KEY:
            continue
        candidate = event.get(protocol.RESULT_KEY)
        if isinstance(candidate, str):
            final_text = candidate
    return final_text


def turn_key(index: int, event: dict[str, Any]) -> str:
    message = event.get(protocol.MESSAGE)
    message_id = message.get(protocol.ID) if isinstance(message, dict) else None
    if isinstance(message_id, str) and message_id:
        return message_id
    request_id = event.get("request_id")
    if isinstance(request_id, str) and request_id:
        return request_id
    return str(index)


@dataclass
class ClaudeTrajectoryBuilder:
    steps: list[TrajectoryStep] = field(default_factory=list)
    seen_calls: set[str] = field(default_factory=set)
    seen_results: set[str] = field(default_factory=set)
    turn_index: dict[str, int] = field(default_factory=dict)

    def add_event(self, index: int, event: dict[str, Any]) -> None:
        event_type = event.get(protocol.TYPE)
        if event_type not in (protocol.ASSISTANT, "user"):
            return
        message = event.get(protocol.MESSAGE)
        if not isinstance(message, dict):
            return
        turn = self._turn(index, event) if event_type == protocol.ASSISTANT else None
        message_blocks = message.get(skills_claude.CONTENT_KEY)
        if not isinstance(message_blocks, list):
            return
        if event_type == protocol.ASSISTANT:
            self.steps.extend(trajectory_claude_blocks.assistant_steps(message_blocks, turn, self.seen_calls))
            return
        self.steps.extend(trajectory_claude_blocks.user_steps(message_blocks, self.seen_results))

    def _turn(self, index: int, event: dict[str, Any]) -> int:
        return self.turn_index.setdefault(
            turn_key(index, event),
            len(self.turn_index),
        )


def trajectory_steps(
    events: Iterable[dict[str, Any]],
) -> tuple[TrajectoryStep, ...]:
    builder = ClaudeTrajectoryBuilder()
    for index, event in enumerate(events):
        builder.add_event(index, event)
    return tuple(builder.steps)
