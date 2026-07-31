# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory usage, turn, step, and record serialization.

One owner for the shape an `agent_trajectory` record has: which run metadata
rides along, which free-text fields are sanitized on the way in, and the order
the variable arrays are charged to the record budget in. The budget order is
part of the shape -- the per-turn array is drawn down before the steps, so a
run with thousands of turns and no steps is bounded the same way a run with
thousands of steps is.

The settings holder arrives on the exit context rather than being resolved
here: it is what the caps are read off and what the record envelope is built
through, so one run's two records -- the baseline `agent_exit` and this one --
are answered for by the same package instance the caller entered on, and a
caps value patched around a call reaches it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orchestrator.observability.analytics.trajectories import models, sanitize
from orchestrator.observability.usage import (
    metrics as usage_metrics,
    trajectory_models as usage_trajectory_models,
)

if TYPE_CHECKING:
    from orchestrator.observability.analytics.recording.models import AgentExitContext


def trajectory_usage(metrics: usage_metrics.UsageMetrics) -> dict[str, Any]:
    run_usage = metrics.to_dict()
    run_usage.pop("backend", None)
    return run_usage


def trajectory_headline(
    context: AgentExitContext,
    trajectory: usage_trajectory_models.AgentTrajectory,
    metrics: usage_metrics.UsageMetrics,
    redact: sanitize.Redactor,
    limits: models.TrajectoryLimits,
) -> models.TrajectoryHeadline:
    return models.TrajectoryHeadline(
        user_input=sanitize.redact_and_truncate(context.prompt, redact, limits),
        system_prompt=sanitize.redact_and_truncate(
            trajectory.system_prompt, redact, limits,
        ),
        output=sanitize.redact_and_truncate(
            trajectory.final_output, redact, limits,
        ),
        run_usage=trajectory_usage(metrics),
    )


def bounded_trajectory_turns(
    trajectory: usage_trajectory_models.AgentTrajectory,
    budget: models.TrajectoryBudget,
) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for turn in trajectory.turns:
        turn_dict = turn.to_dict()
        if not budget.include(turn_dict):
            break
        turns.append(turn_dict)
    return turns


def trajectory_step(
    step: usage_trajectory_models.TrajectoryStep,
    redact: sanitize.Redactor,
    limits: models.TrajectoryLimits,
) -> dict[str, Any]:
    step_dict: dict[str, Any] = {
        "kind": step.kind,
        "name": step.name or None,
        "tool_id": step.tool_id or None,
        "content": sanitize.redact_and_truncate(step.content, redact, limits),
    }
    if step.turn is not None:
        step_dict["turn"] = step.turn
    return step_dict


def bounded_trajectory_steps(
    trajectory: usage_trajectory_models.AgentTrajectory,
    budget: models.TrajectoryBudget,
    redact: sanitize.Redactor,
    limits: models.TrajectoryLimits,
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    if budget.truncated:
        return steps
    for step in trajectory.steps:
        step_dict = trajectory_step(step, redact, limits)
        if not budget.include(step_dict):
            break
        steps.append(step_dict)
    return steps


def build_trajectory_record(
    context: AgentExitContext,
    trajectory: usage_trajectory_models.AgentTrajectory,
    metrics: usage_metrics.UsageMetrics,
    redact: sanitize.Redactor,
) -> dict:
    """Assemble one redacted, truncated `agent_trajectory` record.

    `prompt` becomes the redacted `user_input`; `system_prompt`, each
    step's content, and the final `output` are redacted the same way.
    `metrics` (the same `UsageMetrics` the baseline `agent_exit` record
    already carries) is denormalized into a `run_usage` summary so the
    file-only viewer needs no re-parse; it is `UsageMetrics.to_dict()` minus
    `backend` (already a record field). Its token counts / cost / model name
    are not secret-shaped, so they skip redaction. The claude per-turn
    breakdown rides along as `turns` (empty on codex, whose usage frames are
    cumulative -- `build_record` then drops the key).

    Each step is charged its full *serialized* size -- the JSON metadata
    (`kind` / `name` / `tool_id` / `turn`) plus its truncated content, not
    merely `len(content)` -- so steps with empty or tiny content still consume
    the budget. The per-turn `turns` array is charged and truncated the same
    way (a run with thousands of turns and no steps would otherwise write the
    whole array in full and blow the budget); it is drawn down before the
    steps, so once the running total crosses the record budget the remaining
    turns -- then steps -- are dropped and `truncated` is set. Only the small
    fixed `run_usage` summary is always kept whole. `build_record` drops every
    `None`-valued field, so an absent prompt, empty system prompt, no-trigger
    skill set, or codex's empty per-turn array leaves its key off rather than
    storing a null.
    """
    limits = models.limits_on(context.analytics_package)
    headline = trajectory_headline(context, trajectory, metrics, redact, limits)
    budget = models.TrajectoryBudget(
        headline.serialized_size,
        limits.record_budget,
    )
    turns = bounded_trajectory_turns(trajectory, budget)
    steps = bounded_trajectory_steps(trajectory, budget, redact, limits)
    return context.analytics_package.build_record(
        repo=context.repo,
        issue=context.issue,
        event="agent_trajectory",
        stage=context.stage,
        agent_role=context.agent_role,
        backend=context.backend,
        session_id=context.agent_result.session_id,
        review_round=context.review_round,
        retry_count=context.retry_count,
        user_input=headline.user_input,
        system_prompt=headline.system_prompt,
        tools=list(trajectory.tools) or None,
        skills_triggered=list(trajectory.skills.triggered) or None,
        skills_available=list(trajectory.skills.available) or None,
        run_usage=headline.run_usage,
        turns=turns or None,
        steps=steps,
        output=headline.output,
        truncated=budget.truncated or None,
    )
