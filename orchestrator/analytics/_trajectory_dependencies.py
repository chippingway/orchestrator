# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dependency modules used by the trajectory recording facade."""

from __future__ import annotations

import importlib

_RECORDING = "orchestrator.observability.analytics.recording"

_recording_events = importlib.import_module(f"{_RECORDING}.events")
_recording_io = importlib.import_module(f"{_RECORDING}.io")
_recording_models = importlib.import_module(f"{_RECORDING}.models")
_trajectory_models = importlib.import_module("orchestrator.analytics._trajectory_models")
_trajectory_persistence = importlib.import_module("orchestrator.analytics._trajectory_persistence")
_trajectory_sanitize = importlib.import_module("orchestrator.analytics._trajectory_sanitize")
_trajectory_serialize = importlib.import_module("orchestrator.analytics._trajectory_serialize")


_DEPENDENCIES = (
    _recording_events,
    _recording_io,
    _recording_models,
    _trajectory_models,
    _trajectory_persistence,
    _trajectory_sanitize,
    _trajectory_serialize,
)
