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

TRAJECTORY_PACKAGE = "orchestrator.observability.analytics.trajectories"

TRAJECTORY_API = f"{TRAJECTORY_PACKAGE}.api"

TRAJECTORY_MODELS = f"{TRAJECTORY_PACKAGE}.models"

RETENTION = "orchestrator.observability.analytics.retention"

# Reloaded with the rest so each package instance gets its own recorders, its
# own trajectory sink, and its own by-age prune. `events`, the trajectory
# `api`, and the retention owner are the only ones listed because they are the
# only ones carrying per-instance state -- each captures the instance it was
# imported alongside, while everything beneath them reads the settings off the
# request or the context it is handed. The retention scan and rewrite leaves
# stay put for that reason, and so does `io`: re-executing it would mint a
# second lock for an append and the rewrite to take one each of.
# The recording package above `events` is *re-executed* rather than evicted, so
# its module object survives: a producer imported it under its own name and
# holds that object, and swapping it would leave the producer calling recorders
# this package no longer publishes. The trajectories package is a marker that
# binds nothing, so it needs no such republish.
IMPLEMENTATION_MODULES = (
    RECORDING_EVENTS,
    TRAJECTORY_API,
    RETENTION,
)
