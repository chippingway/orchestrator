# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Temporary compatibility import site for the skill-enumeration package.

The owners live in `orchestrator/skills/`, split by which question a scan
answers: `catalog` for what a target repo offers on its base ref, which is what
the per-tick `repo_skill_catalog` analytics record reports, and `discovery` for
what a single local codex run was loaded with, which is what backfills that
run's `skills_available` / `tools`.

This module re-exports the surface a caller used to reach here for, naming each
owner rather than the package and binding their own objects rather than
rebuilding anything -- but a binding made at import does not follow a later
patch, so a test intercepting one of these targets the module its caller
imported. Nothing on the tick or analytics path reaches this site any more, so
it disappears once the last historical caller names an owner.
"""
from __future__ import annotations

from orchestrator.skills.catalog import (
    _emit_repo_skill_catalog as _emit_repo_skill_catalog,
)
from orchestrator.skills.discovery import (
    _CODEX_OFFERED_TOOLS as _CODEX_OFFERED_TOOLS,
    discover_codex_tools as discover_codex_tools,
    discover_local_skills as discover_local_skills,
)


# The inventory makes the indirect compatibility exports above explicit.
_COMPATIBILITY_EXPORTS = (
    _CODEX_OFFERED_TOOLS,
    _emit_repo_skill_catalog,
    discover_codex_tools,
    discover_local_skills,
)
