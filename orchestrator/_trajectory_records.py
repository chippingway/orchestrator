# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable trajectory record models and JSONL read entry points.

The vocabulary and the views are the owners' own objects, republished here
because this is the import site their API is documented at. The four entry
points below are this module's own, each for one reason. `parse_record` binds a
caller's `obj` / `seq` against a declared signature and hands the owner its own
`sequence` keyword. The other three are the world binding: each passes the
analytics package this module captured at its own import to the owner that
reads a knob off it, so a reader rebuilt against a different environment
resolves that environment's path, and a patch on the package a caller holds
reaches every read made through it.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Optional

from orchestrator import analytics
from orchestrator.observability.trajectory_viewer import constants, log_paths, parsing, reading
from orchestrator.observability.trajectory_viewer import models as view_models
from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun as TrajectoryRun


TRAJECTORY_EVENT = constants.TRAJECTORY_EVENT
TIMELINE_PROMPT = constants.TIMELINE_PROMPT
TIMELINE_OUTPUT = constants.TIMELINE_OUTPUT
UNCONFIGURED_LOG_MESSAGE = constants.UNCONFIGURED_LOG_MESSAGE
RunUsageView = view_models.RunUsageView
TimelineEntry = view_models.TimelineEntry
TrajectoryStepView = view_models.TrajectoryStepView
TurnUsageView = view_models.TurnUsageView
RECORD_SIGNATURE = inspect.Signature(
    parameters=(
        inspect.Parameter("obj", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        inspect.Parameter("seq", inspect.Parameter.KEYWORD_ONLY),
    )
)


def resolve_log_path() -> Optional[Path]:
    """Return the trajectory log path configured for this reader world."""
    return log_paths.configured_path(analytics)


def log_unconfigured_message() -> Optional[str]:
    """Return the opt-in banner when the trajectory sink is disabled."""
    return log_paths.unconfigured_message(analytics)


def parse_record(*args: Any, **kwargs: Any) -> Optional[TrajectoryRun]:
    """Parse one decoded JSONL object through the historical call shape."""
    bound = RECORD_SIGNATURE.bind(*args, **kwargs)
    return parsing.parse_record(
        bound.arguments["obj"],
        sequence=bound.arguments["seq"],
    )


def read_trajectories(path: Optional[Path] = None) -> list[TrajectoryRun]:
    """Read agent-trajectory records newest first, skipping malformed lines."""
    return reading.read_trajectories(log_paths.resolve_path(analytics, path))


parse_record.__signature__ = RECORD_SIGNATURE
