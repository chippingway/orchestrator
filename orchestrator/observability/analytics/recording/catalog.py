# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Codex capability discovery for the records a run's exit earns.

Codex's JSON stream reports what a run *did*, never what it was offered, so
the two capability sets an enabled sink wants -- the skills the worktree
carried, with the source level that defined each one, and the baseline tools
the CLI exposes -- are read out of band from the filesystem instead. Each is
read only when a sink that keeps it is on, and the whole discovery is
fail-open: a run's baseline event is worth more than the enrichment, so a
discovery failure leaves the fields empty rather than losing the record.

The discovery owners are reached inside the call rather than bound here, so
the module a patch aims at is `orchestrator.skills.discovery` -- and so
nothing on this path charges an importer for the skill scanner.
"""

from __future__ import annotations

from typing import Any

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics import sink
from orchestrator.observability.analytics.recording.models import (
    AgentExitContext,
    CodexCatalog,
)

# The name/level pairs the scanner hands back, spelled structurally rather
# than imported: this module names `orchestrator.skills.discovery` in exactly
# one place, the deferred import inside the call, which is what keeps that
# module the one a patch aims at.
_SkillSources = tuple[Any, ...]


def discover_codex_skill_sources(
    context: AgentExitContext,
    discovery: Any,
) -> _SkillSources:
    """Read Codex's offered skills and their levels when either sink needs them."""
    settings = analytics_config.live_settings()
    if context.cwd is None or not (settings.track_skill_triggers or settings.trajectory_log_path is not None):
        return ()
    return tuple(discovery.discover_local_skill_sources(context.cwd))


def discover_codex_tools(
    context: AgentExitContext,
    discovery: Any,
) -> list[str] | None:
    """Read Codex's baseline tools only for trajectory records."""
    settings = analytics_config.live_settings()
    if settings.trajectory_log_path is None:
        return None
    return list(discovery.discover_codex_tools()) or None


def populate_codex_catalog(
    context: AgentExitContext,
    catalog: CodexCatalog,
) -> None:
    """Fill Codex capabilities in discovery order.

    The names and the levels are projected from one scan rather than read
    twice, so the offered set and its provenance describe the same worktree.
    """
    from orchestrator.skills import discovery

    skill_sources = discover_codex_skill_sources(context, discovery)
    catalog.available_skills = [source.name for source in skill_sources] or None
    catalog.skill_levels = {
        source.name: source.level for source in skill_sources
    } or None
    catalog.tools = discover_codex_tools(context, discovery)


def discover_codex_catalog(context: AgentExitContext) -> CodexCatalog:
    """Discover Codex capabilities needed by enabled analytics sinks."""
    catalog = CodexCatalog()
    if context.backend != "codex":
        return catalog
    try:
        populate_codex_catalog(context, catalog)
    except Exception:
        sink.log.exception(
            "issue=#%d analytics: codex out-of-band discovery failed; leaving skills_available / levels / tools empty",
            context.issue,
        )
    return catalog
