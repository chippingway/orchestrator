# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Codex capability discovery for analytics agent records."""

from __future__ import annotations

from typing import Any, Optional

from orchestrator.analytics._recording_models import (
    _AgentExitContext,
    _CodexCatalog,
)


def _discover_codex_skills(
    context: _AgentExitContext,
    discovery: Any,
) -> Optional[list[str]]:
    """Read Codex's offered skills when either sink needs them."""
    settings = context.analytics_package
    if context.cwd is None or not (settings.TRACK_SKILL_TRIGGERS or settings.TRAJECTORY_LOG_PATH is not None):
        return None
    return list(discovery.discover_local_skills(context.cwd)) or None


def _discover_codex_tools(
    context: _AgentExitContext,
    discovery: Any,
) -> Optional[list[str]]:
    """Read Codex's baseline tools only for trajectory records."""
    if context.analytics_package.TRAJECTORY_LOG_PATH is None:
        return None
    return list(discovery.discover_codex_tools()) or None


def _populate_codex_catalog(
    context: _AgentExitContext,
    catalog: _CodexCatalog,
) -> None:
    """Fill Codex capabilities in discovery order."""
    from orchestrator.skills import discovery

    catalog.available_skills = _discover_codex_skills(context, discovery)
    catalog.tools = _discover_codex_tools(context, discovery)


def _discover_codex_catalog(context: _AgentExitContext) -> _CodexCatalog:
    """Discover Codex capabilities needed by enabled analytics sinks."""
    catalog = _CodexCatalog()
    if context.backend != "codex":
        return catalog
    try:
        _populate_codex_catalog(context, catalog)
    except Exception:
        context.analytics_package.log.exception(
            "issue=#%d analytics: codex out-of-band discovery failed; leaving skills_available / tools empty",
            context.issue,
        )
    return catalog
