# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Owner-built steps and runs the model and view tests are written against."""
from __future__ import annotations

from typing import Any

from orchestrator.observability.trajectory_viewer import models, runs


TOOL_CALL = "tool_call"

TOOL_RESULT = "tool_result"

ASSISTANT_MESSAGE = "assistant_message"

TOOL_BASH = "Bash"

TOOL_SKILL = "Skill"

TS = "2026-06-20T10:00:00+00:00"

REPO = "acme/widgets"

ISSUE = 42


def step(kind: str, **fields: Any) -> models.TrajectoryStepView:
    """One normalized step, defaulted the way a parsed record leaves it."""
    return models.TrajectoryStepView(kind=kind, **fields)


def run(**fields: Any) -> runs.TrajectoryRun:
    """A run carrying the identity every record has, overridable per test.

    The four identity fields are what the sink writes on every line, so a test
    about a timeline or a tally names only what it is actually about.
    """
    record = {"seq": 0, "ts": TS, "repo": REPO, "issue": ISSUE}
    record.update(fields)
    return runs.TrajectoryRun(**record)
