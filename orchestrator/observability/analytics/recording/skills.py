# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Skill-field normalization for the records a run's exit earns.

The opt-in half of an `agent_exit`: what the skill-evidence parser reports,
turned into the optional keys the event carries. Every field is dropped when
empty, so a run with nothing to report keeps the record shape a default
install writes, and the whole read is guarded -- the switch is observability,
so a parser failure costs the skill keys rather than the baseline event.
"""

from __future__ import annotations

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics import sink
from orchestrator.observability.analytics.recording.models import (
    AgentExitContext,
    AgentExitSkillFields,
    CodexCatalog,
)
from orchestrator.observability.usage import skills as usage_skills


def normalize_agent_exit_skills(
    parsed_skills: usage_skills.SkillTriggers,
    codex_catalog: CodexCatalog,
) -> AgentExitSkillFields:
    """Convert parser output into optional event fields.

    Incidental references stay out of `skills_triggered` / the count (and thus
    the `skill_triggered` audit events) -- they ride the separate
    `skills_incidental` / `skills_incidental_count` keys. `skills_evidence`
    persists the per-load tier the parser assigned.
    """
    skills_triggered = list(parsed_skills.triggered) or None
    skills_triggered_count = sum(parsed_skills.trigger_counts.values()) if skills_triggered else None
    skills_available = list(parsed_skills.available) or codex_catalog.available_skills
    skills_incidental = list(parsed_skills.incidental) or None
    skills_incidental_count = sum(parsed_skills.incidental_counts.values()) if skills_incidental else None
    return AgentExitSkillFields(
        skills_triggered=skills_triggered,
        skills_triggered_count=skills_triggered_count,
        skills_available=skills_available,
        skills_evidence=dict(parsed_skills.evidence) or None,
        skills_incidental=skills_incidental,
        skills_incidental_count=skills_incidental_count,
    )


def read_agent_exit_skills(
    context: AgentExitContext,
    codex_catalog: CodexCatalog,
) -> AgentExitSkillFields:
    """Parse and normalize skill fields for an enabled run."""
    parsed_skills = usage_skills.parse_agent_skills(
        context.backend,
        context.agent_result.stdout,
    )
    return normalize_agent_exit_skills(parsed_skills, codex_catalog)


def parse_agent_exit_skills(
    context: AgentExitContext,
    codex_catalog: CodexCatalog,
) -> AgentExitSkillFields:
    """Parse opt-in skill fields without risking the baseline event."""
    if not analytics_config.live_settings().track_skill_triggers:
        return AgentExitSkillFields()
    try:
        return read_agent_exit_skills(context, codex_catalog)
    except Exception:
        sink.log.exception(
            "issue=#%d analytics: parse_agent_skills(%s) failed; emitting record without skill fields",
            context.issue,
            context.backend,
        )
        return AgentExitSkillFields()
