# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Skill query family, beside the historical import site for its neighbors.

The three skill reads are still owned here: what a skill was triggered at, the
per-repository matrix of that reach, and the sessions that adopted it. The four
beside them are the query owners' own functions, so a call made here runs the
SQL, the projections, and the short circuits the breakdown family is maintained
by; the underscored names among them are the projections that family published
while this hub owned them, bound to the owner's object rather than re-derived.
"""

from __future__ import annotations

from typing import Any

from orchestrator.analytics._read_skill_adoption import (
    SKILL_ADOPTION_ROW_LIMIT as SKILL_ADOPTION_ROW_LIMIT,
    _skill_adoption_rows,
)
from orchestrator.analytics._read_skill_matrix import (
    SKILL_MATRIX_ROW_LIMIT as SKILL_MATRIX_ROW_LIMIT,
    _skill_trigger_matrix_rows,
)
from orchestrator.analytics._read_skill_trigger_rates import (
    _skill_trigger_rate_rows,
)
from orchestrator.observability.analytics.query.backend_tokens import (
    backend_daily_token_rows as _backend_daily_token_rows,
)
from orchestrator.observability.analytics.query.breakdown_reads import (
    get_backend_daily_tokens as get_backend_daily_tokens,
    get_cost_coverage as get_cost_coverage,
    get_hourly_heatmap as get_hourly_heatmap,
    get_review_round_breakdown as get_review_round_breakdown,
)
from orchestrator.observability.analytics.query.conditions import agent_event_excluded
from orchestrator.observability.analytics.query.cost_coverage import (
    cost_coverage_rows as _cost_coverage_rows,
)
from orchestrator.observability.analytics.query.hourly_heatmaps import (
    hourly_heatmap_rows as _hourly_heatmap_rows,
)
from orchestrator.observability.analytics.query.requests import (
    FILTERED_READ_SIGNATURE,
    LIMITED_READ_SIGNATURE,
    bind_read_request,
    resolve_read_query,
    window_filters,
)
from orchestrator.observability.analytics.query.review_rounds import (
    review_round_rows as _review_round_rows,
)
from orchestrator.observability.analytics.query.row_cells import cost_cell as _cost_cell
from orchestrator.observability.analytics.query.skill_models import (
    SkillAdoptionRow,
    SkillTriggerMatrixRow,
    SkillTriggerRateRow,
)


_COMPATIBILITY_EXPORTS = (
    _cost_cell,
    SKILL_ADOPTION_ROW_LIMIT,
    SKILL_MATRIX_ROW_LIMIT,
    _backend_daily_token_rows,
    _cost_coverage_rows,
    _hourly_heatmap_rows,
    _review_round_rows,
    get_backend_daily_tokens,
    get_cost_coverage,
    get_hourly_heatmap,
    get_review_round_breakdown,
)


_SKILL_TRIGGER_RATE_SIGNATURE = FILTERED_READ_SIGNATURE.replace(
    return_annotation="list[SkillTriggerRateRow]",
)
_SKILL_TRIGGER_MATRIX_SIGNATURE = LIMITED_READ_SIGNATURE.replace(
    return_annotation="list[SkillTriggerMatrixRow]",
)
_SKILL_ADOPTION_SIGNATURE = LIMITED_READ_SIGNATURE.replace(
    return_annotation="list[SkillAdoptionRow]",
)


def get_skill_trigger_rates(
    *args: Any,
    **kwargs: Any,
) -> list[SkillTriggerRateRow]:
    """Return skill-trigger rates grouped by agent role and backend."""
    request = bind_read_request(_SKILL_TRIGGER_RATE_SIGNATURE, args, kwargs)
    query = resolve_read_query(request)
    if not query.available:
        return []
    if agent_event_excluded(request.filters.events):
        return []
    return _skill_trigger_rate_rows(query, window_filters(request))


get_skill_trigger_rates.__signature__ = _SKILL_TRIGGER_RATE_SIGNATURE


def get_skill_trigger_matrix(
    *args: Any,
    **kwargs: Any,
) -> list[SkillTriggerMatrixRow]:
    """Return per-skill trigger cells for each repository cohort."""
    request = bind_read_request(_SKILL_TRIGGER_MATRIX_SIGNATURE, args, kwargs)
    selected_limit = int(request.options.limit or 0)
    query = resolve_read_query(request)
    if not query.available:
        return []
    if agent_event_excluded(request.filters.events):
        return []
    return _skill_trigger_matrix_rows(
        query,
        window_filters(request),
        selected_limit,
    )


get_skill_trigger_matrix.__signature__ = _SKILL_TRIGGER_MATRIX_SIGNATURE


def get_skill_adoption(*args: Any, **kwargs: Any) -> list[SkillAdoptionRow]:
    """Return per-session skill adoption cells for each repository cohort."""
    request = bind_read_request(_SKILL_ADOPTION_SIGNATURE, args, kwargs)
    selected_limit = int(request.options.limit or 0)
    query = resolve_read_query(request)
    if not query.available:
        return []
    if agent_event_excluded(request.filters.events):
        return []
    return _skill_adoption_rows(
        query,
        window_filters(request),
        selected_limit,
    )


get_skill_adoption.__signature__ = _SKILL_ADOPTION_SIGNATURE
