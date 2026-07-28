# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Temporary compatibility import site for the usage-parsing package.

The parsers live in `orchestrator/observability/usage/`, split across owners
by what a provider payload has to be turned into: `metrics` for the token,
model, turn, and cost surface, `skills` for the skill evidence one run left,
and `trajectory` over `trajectory_models` for the ordered timeline and its
claude-only per-turn usage. That package publishes the same fourteen names as
its narrow public surface: the nine parsers, a per-backend trio each, and the
five result types they hand back.

This module re-exports that surface so a historical caller keeps importing it
from `orchestrator.usage`. It names each owner rather than the package and
binds their own objects rather than rebuilding anything -- but a binding made
at import does not follow a later patch, so a test intercepting a parser
targets the module its caller imported. This site disappears once the last
caller names the package.
"""
from __future__ import annotations

from orchestrator.observability.usage.metrics import (
    UsageMetrics as UsageMetrics,
    parse_agent_usage as parse_agent_usage,
    parse_claude_usage as parse_claude_usage,
    parse_codex_usage as parse_codex_usage,
)
from orchestrator.observability.usage.skills import (
    SkillTriggers as SkillTriggers,
    parse_agent_skills as parse_agent_skills,
    parse_claude_skills as parse_claude_skills,
    parse_codex_skills as parse_codex_skills,
)
from orchestrator.observability.usage.trajectory import (
    parse_agent_trajectory as parse_agent_trajectory,
    parse_claude_trajectory as parse_claude_trajectory,
    parse_codex_trajectory as parse_codex_trajectory,
)
from orchestrator.observability.usage.trajectory_models import (
    AgentTrajectory as AgentTrajectory,
    TrajectoryStep as TrajectoryStep,
    TurnUsage as TurnUsage,
)


# The inventory makes the indirect compatibility exports above explicit.
_COMPATIBILITY_EXPORTS = (
    UsageMetrics,
    parse_agent_usage,
    parse_claude_usage,
    parse_codex_usage,
    SkillTriggers,
    parse_agent_skills,
    parse_claude_skills,
    parse_codex_skills,
    AgentTrajectory,
    TrajectoryStep,
    TurnUsage,
    parse_agent_trajectory,
    parse_claude_trajectory,
    parse_codex_trajectory,
)
