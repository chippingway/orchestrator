# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics package export and reload inventory."""

from __future__ import annotations

EXPORTED_NAMES = (
    "ANALYTICS_DB_URL",
    "ANALYTICS_LOG_PATH",
    "ANALYTICS_RETENTION_DAYS",
    "TRACK_SKILL_TRIGGERS",
    "TRAJECTORY_LOG_PATH",
    "TRAJECTORY_RETENTION_DAYS",
    "append_record",
    "append_trajectory_record",
    "build_record",
    "config",
    "prune_old_records",
    "prune_trajectory_records",
    "prune_with_retention_logging",
    "record_agent_exit",
    "record_repo_skill_catalog",
    "record_stage_enter",
    "record_stage_evaluation",
)

RECORDING_PACKAGE = "orchestrator.observability.analytics.recording"

RECORDING_EVENTS_ATTRIBUTE = "events"

RECORDING_EVENTS = f"{RECORDING_PACKAGE}.{RECORDING_EVENTS_ATTRIBUTE}"

# Reloaded with the rest so each package instance gets its own recorders.
# `events` is the only recording owner listed because it is the only one
# carrying per-instance state -- it captures the instance it was imported
# alongside, while everything beneath it reads settings off the request it is
# handed. The package above it is *re-executed* rather than evicted, so its
# module object survives: a producer imported it under its own name and holds
# that object, and swapping it would leave the producer calling recorders this
# package no longer publishes.
IMPLEMENTATION_MODULES = (
    RECORDING_EVENTS,
    "orchestrator.analytics._retention",
    "orchestrator.analytics._retention_rewrite",
    "orchestrator.analytics._retention_scan",
    "orchestrator.analytics._trajectories",
    "orchestrator.analytics._trajectory_dependencies",
    "orchestrator.analytics._trajectory_models",
    "orchestrator.analytics._trajectory_persistence",
    "orchestrator.analytics._trajectory_sanitize",
    "orchestrator.analytics._trajectory_serialize",
)
