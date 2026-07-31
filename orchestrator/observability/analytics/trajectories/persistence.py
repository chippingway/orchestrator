# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory parsing, Codex enrichment, and fail-open persistence.

One owner for the whole opt-in write: whether it happens at all, what the
stream is parsed into, what a Codex run's missing capabilities are backfilled
from, and the guard the entire block rides. They sit together because they are
one decision -- the sink being off is what makes the parse never run, and the
parse failing is what the guard exists to swallow.

The settings holder arrives on the exit context: the knob that gates this and
the append that ends it are both answered by the package instance the caller
entered on, which is what keeps one run's two records on the same instance.
The redactor and the logger are named inside the call, so the append path
costs neither until the sink an operator turned on has something to write.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics.trajectories.serialize import (
    build_trajectory_record,
)
from orchestrator.observability.usage import (
    metrics as usage_metrics,
    trajectory as usage_trajectory,
    trajectory_models as usage_trajectory_models,
)

if TYPE_CHECKING:
    from orchestrator.observability.analytics.recording.models import (
        AgentExitContext,
        CodexCatalog,
    )


def codex_trajectory_changes(
    trajectory: usage_trajectory_models.AgentTrajectory,
    catalog: CodexCatalog,
) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    if catalog.available_skills and not trajectory.skills.available:
        changes["skills"] = replace(
            trajectory.skills,
            available=tuple(catalog.available_skills),
        )
    if catalog.tools and not trajectory.tools:
        changes["tools"] = tuple(catalog.tools)
    return changes


def agent_trajectory(
    context: AgentExitContext,
    catalog: CodexCatalog,
) -> usage_trajectory_models.AgentTrajectory:
    trajectory = usage_trajectory.parse_agent_trajectory(
        context.backend,
        context.agent_result.stdout,
    )
    if context.backend != "codex":
        return trajectory
    changes = codex_trajectory_changes(trajectory, catalog)
    if not changes:
        return trajectory
    return replace(trajectory, **changes)


def persist_trajectory_record(
    context: AgentExitContext,
    metrics: usage_metrics.UsageMetrics,
    codex_catalog: CodexCatalog,
) -> None:
    """Build and append the denormalized trajectory record.

    The redactor is reached inside the write rather than bound at import: it
    is the one thing this owner needs from outside the observability tree, and
    naming it here keeps a producer that imports the recording path from
    paying for the credential owner behind a sink that is off by default.
    """
    from orchestrator.config import credentials

    trajectory = agent_trajectory(context, codex_catalog)
    context.analytics_package.append_trajectory_record(
        build_trajectory_record(
            context,
            trajectory,
            metrics,
            credentials.redact_secrets,
        ),
    )


def maybe_record_trajectory(
    context: AgentExitContext,
    metrics: usage_metrics.UsageMetrics,
    codex_catalog: CodexCatalog,
) -> None:
    """Parse, redact, truncate, and append one trajectory record -- gated on
    the opt-in `TRAJECTORY_LOG_PATH` and wrapped in its own fail-open guard.

    A no-op when the trajectory sink is disabled (the default), so the
    orchestrator-built prompt (`user_input`) -- and the parse/redact work
    itself -- happens ONLY when an operator turned the sink on. `metrics` is
    the `UsageMetrics` `record_agent_exit` already parsed for the baseline
    `agent_exit` record; it is threaded through (never re-parsed) so the
    trajectory record can carry a denormalized `run_usage` summary. The whole
    block rides a dedicated try/except: a parser bug, an unredactable
    payload, or a sink IO failure logs and is swallowed so it can never drop
    the baseline `agent_exit` usage / cost record or the `skill_triggered`
    audit events, all of which were already produced before this runs.

    `codex_catalog` carries the out-of-band offered-skills and offered-tools
    sets `record_agent_exit` discovered for a codex run (empty for claude,
    whose offered sets already ride its stream). When present they backfill
    the codex trajectory's otherwise-empty
    `skills.available` / `tools` so the trajectory viewer's "Skills available"
    and "Tools offered" chips match a claude run's; a non-empty stream-parsed
    set is never overridden.
    """
    if analytics_config.settings_on(context.analytics_package).trajectory_log_path is None:
        return
    try:
        persist_trajectory_record(context, metrics, codex_catalog)
    except Exception:
        from orchestrator.observability.analytics.recording import events

        events.log.exception(
            "issue=#%d analytics: trajectory record(%s) failed; baseline agent_exit record is unaffected",
            context.issue,
            context.backend,
        )
