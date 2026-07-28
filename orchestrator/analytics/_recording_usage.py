# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Usage parsing for completed analytics agent runs."""

from __future__ import annotations

from typing import Optional

from orchestrator.analytics._recording_models import _AgentExitContext
from orchestrator.observability.usage import metrics as usage_metrics


def _parse_agent_exit_usage(
    context: _AgentExitContext,
) -> Optional[usage_metrics.UsageMetrics]:
    """Parse usage and attach it to the result, failing open on bad streams."""
    try:
        metrics = usage_metrics.parse_agent_usage(
            context.backend,
            context.agent_result.stdout,
            fallback_model=context.fallback_model,
        )
    except Exception:
        context.analytics_package.log.exception(
            "issue=#%d analytics: parse_agent_usage(%s) failed; skipping record",
            context.issue,
            context.backend,
        )
        return None
    context.agent_result.usage = metrics
    return metrics
