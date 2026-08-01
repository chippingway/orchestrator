# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a run's tallies and its money read as, projected off the record.

Every accessor here answers from the run summary the sink already wrote rather
than re-adding the per-turn rows, because that summary is the authoritative
figure a provider reported and the turns are a claude-only detail a codex
record does not carry at all. A record written before the usage feature has no
summary, so each projection names the empty answer for its own type -- zero
tokens, no model, an unpriced cost -- and none of them raises.

The per-turn lookup is the one that reads the turns: it goes through the run's
cached index so a page walking a timeline can ask for each entry's turn in
turn without rescanning the tuple per entry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from orchestrator.observability.trajectory_viewer.models import TurnUsageView

if TYPE_CHECKING:
    from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun


def tool_calls(run: TrajectoryRun) -> int:
    return sum(1 for step in run.steps if step.is_call)


def step_count(run: TrajectoryRun) -> int:
    return len(run.steps)


def model(run: TrajectoryRun) -> str:
    if run.run_usage is None or not run.run_usage.models:
        return ""
    return run.run_usage.models[0]


def cost_usd(run: TrajectoryRun) -> Optional[float]:
    if run.run_usage is None:
        return None
    return run.run_usage.cost_usd


def cost_source(run: TrajectoryRun) -> str:
    if run.run_usage is None:
        return ""
    return run.run_usage.cost_source


def total_tokens(run: TrajectoryRun) -> int:
    if run.run_usage is None:
        return 0
    return run.run_usage.total_tokens


def usage_for_turn(
    run: TrajectoryRun,
    turn: Optional[int],
) -> Optional[TurnUsageView]:
    if turn is None:
        return None
    return run._turn_map.get(turn)
