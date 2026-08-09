# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Where each name this package forwards is defined."""

from __future__ import annotations

from types import MappingProxyType

_OWNERS = "orchestrator.observability.analytics"

_RECORDING = f"{_OWNERS}.recording"

_RETENTION = f"{_OWNERS}.retention"

_SETTINGS = f"{_OWNERS}.settings"

_TRAJECTORY_API = f"{_OWNERS}.trajectories.api"

# One entry per historical member, pointing at the module that defines it now.
# Resolved per access rather than bound once, so a knob patched on the
# `settings` owner -- where every producer reads it -- is what a caller
# reaching this package observes.
MEMBER_OWNERS = MappingProxyType({
    "ANALYTICS_DB_URL": _SETTINGS,
    "ANALYTICS_LOG_PATH": _SETTINGS,
    "ANALYTICS_RETENTION_DAYS": _SETTINGS,
    "TRACK_SKILL_TRIGGERS": _SETTINGS,
    "TRAJECTORY_LOG_PATH": _SETTINGS,
    "TRAJECTORY_RETENTION_DAYS": _SETTINGS,
    "append_record": _RECORDING,
    "append_trajectory_record": _TRAJECTORY_API,
    "build_record": _RECORDING,
    "prune_old_records": _RETENTION,
    "prune_trajectory_records": _RETENTION,
    "prune_with_retention_logging": _RETENTION,
    "record_agent_exit": _RECORDING,
    "record_repo_skill_catalog": _RECORDING,
    "record_stage_enter": _RECORDING,
    "record_stage_evaluation": _RECORDING,
})

# The one historical name that is a module rather than a member of one.
MODULE_EXPORTS = MappingProxyType({"config": "orchestrator.config"})

EXPORTED_NAMES = tuple(sorted(set(MEMBER_OWNERS) | set(MODULE_EXPORTS)))
