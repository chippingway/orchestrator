# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Provider trajectory parser entry points over the shared records."""

from __future__ import annotations

from orchestrator.observability.usage import (
    event_stream,
    protocol,
    trajectory_claude_stream,
    trajectory_claude_turns,
    trajectory_codex,
)
from orchestrator.observability.usage.skills import (
    parse_claude_skills,
    parse_codex_skills,
)
from orchestrator.observability.usage.trajectory_models import AgentTrajectory


def parse_claude_trajectory(stdout: str) -> AgentTrajectory:
    """Classify a Claude stream-json run's trajectory."""
    events = event_stream.iter_events(stdout)
    return AgentTrajectory(
        backend=protocol.CLAUDE,
        tools=trajectory_claude_stream.offered_tools(events),
        skills=parse_claude_skills(stdout),
        steps=trajectory_claude_stream.trajectory_steps(events),
        final_output=trajectory_claude_stream.final_output(events),
        turns=trajectory_claude_turns.claude_turn_usage(events),
    )


def parse_codex_trajectory(stdout: str) -> AgentTrajectory:
    """Classify a Codex JSON run's trajectory."""
    events = event_stream.iter_events(stdout)
    return AgentTrajectory(
        backend=protocol.CODEX,
        skills=parse_codex_skills(stdout),
        steps=trajectory_codex.trajectory_steps(events),
        final_output=trajectory_codex.final_output(events),
    )


def parse_agent_trajectory(backend: str, stdout: str) -> AgentTrajectory:
    """Dispatch trajectory parsing by agent backend."""
    if backend == protocol.CLAUDE:
        return parse_claude_trajectory(stdout)
    if backend == protocol.CODEX:
        return parse_codex_trajectory(stdout)
    raise ValueError(
        f"unknown agent backend {backend!r}; expected 'claude' or 'codex'",
    )
