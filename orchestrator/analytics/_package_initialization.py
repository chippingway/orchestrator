# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Fresh per-package analytics implementations and export values."""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from orchestrator.agents import AgentResult
from orchestrator.analytics._package_manifest import (
    EXPORTED_NAMES,
    IMPLEMENTATION_MODULES,
    RECORDING_EVENTS,
    RECORDING_EVENTS_ATTRIBUTE,
    RECORDING_PACKAGE,
    RETENTION,
    TRAJECTORY_API,
    TRAJECTORY_MODELS,
)
from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics.recording.io import (
    ANALYTICS_FILE_LOCK,
    TRAJECTORY_FILE_LOCK,
)


@dataclass(frozen=True)
class _AnalyticsModules:
    recording: ModuleType
    recording_events: ModuleType
    trajectory_api: ModuleType
    trajectory_models: ModuleType
    retention: ModuleType


def _evict_implementations() -> None:
    for module_name in IMPLEMENTATION_MODULES:
        sys.modules.pop(module_name, None)


def _rebuilt_recording() -> ModuleType:
    """Republish the canonical recording package over a fresh `events`.

    The package is re-executed in place rather than evicted and re-imported,
    so its module object outlives every reload. That identity is the contract:
    a producer names the package at its own import and keeps the object it got
    back, so replacing it would strand the producer on recorders answering for
    a package instance nobody holds any more, and put a patch aimed at the
    canonical module out of that producer's path.

    `events` underneath it *is* replaced, because the settings holder it
    captures at import is the one thing that has to differ per instance. The
    eviction drops it from `sys.modules`; dropping it off the package too is
    what makes the re-execution import a fresh one rather than rebind the
    attribute an earlier import left behind.
    """
    package = sys.modules.get(RECORDING_PACKAGE)
    if package is None:
        return importlib.import_module(RECORDING_PACKAGE)
    package.__dict__.pop(RECORDING_EVENTS_ATTRIBUTE, None)
    return importlib.reload(package)


def _load_modules() -> _AnalyticsModules:
    _evict_implementations()
    return _AnalyticsModules(
        recording=_rebuilt_recording(),
        recording_events=importlib.import_module(RECORDING_EVENTS),
        trajectory_api=importlib.import_module(TRAJECTORY_API),
        trajectory_models=importlib.import_module(TRAJECTORY_MODELS),
        retention=importlib.import_module(RETENTION),
    )


def _public_exports(modules: _AnalyticsModules) -> dict[str, Any]:
    from orchestrator import config

    recording = modules.recording
    retention = modules.retention
    return {
        "append_record": recording.append_record,
        "append_trajectory_record": modules.trajectory_api.append_trajectory_record,
        "build_record": recording.build_record,
        "config": config,
        "prune_old_records": retention.prune_old_records,
        "prune_trajectory_records": retention.prune_trajectory_records,
        "prune_with_retention_logging": retention.prune_with_retention_logging,
        "record_agent_exit": recording.record_agent_exit,
        "record_repo_skill_catalog": recording.record_repo_skill_catalog,
        "record_stage_enter": recording.record_stage_enter,
        "record_stage_evaluation": recording.record_stage_evaluation,
    }


def _compatibility_exports(modules: _AnalyticsModules) -> dict[str, Any]:
    """Bind the private names a caller patches or observes a sink through.

    The three trajectory caps are bound from the owner that declares them and
    read back off this package by every write, so shrinking one here is what
    bounds the next record. Both sink locks come from the `io` owner rather
    than from the appends that take them: no reload rebuilds it, so the object
    bound here is the one an append held across a rebuild still takes -- and
    the one each prune serializes against.
    """
    events = modules.recording_events
    trajectory_models = modules.trajectory_models
    return {
        "AgentResult": AgentResult,
        "_FILE_LOCK": ANALYTICS_FILE_LOCK,
        "log": events.log,
        "os": os,
        "_TRAJECTORY_FIELD_HEAD": trajectory_models.TRAJECTORY_FIELD_HEAD,
        "_TRAJECTORY_FIELD_TAIL": trajectory_models.TRAJECTORY_FIELD_TAIL,
        "_TRAJECTORY_FILE_LOCK": TRAJECTORY_FILE_LOCK,
        "_TRAJECTORY_RECORD_BUDGET": trajectory_models.TRAJECTORY_RECORD_BUDGET,
    }


def initialize_package(package: ModuleType) -> None:
    """Populate one analytics package instance with a coherent module set."""
    modules = _load_modules()
    exported_values = analytics_config.parsed_settings()
    exported_values.update(_public_exports(modules))
    exported_values.update(_compatibility_exports(modules))
    exported_values["__all__"] = EXPORTED_NAMES
    exported_values["_ANALYTICS_EXPORTS_INITIALIZED"] = True
    package.__dict__.update(exported_values)
