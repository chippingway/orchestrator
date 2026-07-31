# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Codex capability discovery for the records a run's exit earns.

Codex's JSON stream reports what a run *did*, never what it was offered, so
the two capability sets an enabled sink wants -- the skills the worktree
carried and the baseline tools the CLI exposes -- are read out of band from
the filesystem instead. Each is read only when a sink that keeps it is on, and
the whole discovery is fail-open: a run's baseline event is worth more than
the enrichment, so a discovery failure leaves the fields empty rather than
losing the record.

The discovery owners are reached inside the call rather than bound here, so
the module a patch aims at is `orchestrator.skills.discovery` -- and so
nothing on this path charges an importer for the skill scanner.
"""

from __future__ import annotations

from typing import Any, Optional

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics.recording.models import (
    AgentExitContext,
    CodexCatalog,
)


def discover_codex_skills(
    context: AgentExitContext,
    discovery: Any,
) -> Optional[list[str]]:
    """Read Codex's offered skills when either sink needs them."""
    settings = analytics_config.settings_on(context.analytics_package)
    if context.cwd is None or not (settings.track_skill_triggers or settings.trajectory_log_path is not None):
        return None
    return list(discovery.discover_local_skills(context.cwd)) or None


def discover_codex_tools(
    context: AgentExitContext,
    discovery: Any,
) -> Optional[list[str]]:
    """Read Codex's baseline tools only for trajectory records."""
    settings = analytics_config.settings_on(context.analytics_package)
    if settings.trajectory_log_path is None:
        return None
    return list(discovery.discover_codex_tools()) or None


def populate_codex_catalog(
    context: AgentExitContext,
    catalog: CodexCatalog,
) -> None:
    """Fill Codex capabilities in discovery order."""
    from orchestrator.skills import discovery

    catalog.available_skills = discover_codex_skills(context, discovery)
    catalog.tools = discover_codex_tools(context, discovery)


def discover_codex_catalog(context: AgentExitContext) -> CodexCatalog:
    """Discover Codex capabilities needed by enabled analytics sinks."""
    catalog = CodexCatalog()
    if context.backend != "codex":
        return catalog
    try:
        populate_codex_catalog(context, catalog)
    except Exception:
        context.analytics_package.log.exception(
            "issue=#%d analytics: codex out-of-band discovery failed; leaving skills_available / tools empty",
            context.issue,
        )
    return catalog
