# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The three reads answered from the `extras` blob the rollup does not carry.

Each one binds its keyword call against the signature its family is declared
with, resolves the connection behind it, and hands the filtered window to the
projection owner beside it. Every signature is a shared one re-annotated with
what the read returns, so the vocabulary a caller writes stays declared once
while the return type stays readable on the function it belongs to.

What these three have in common is where the fact lives. A skill name, the set
a repository offered, and the count one run loaded are all recorded inside an
`agent_exit` row's `extras` JSONB, which neither the day-bucketed rollup nor
the agent-run view above the events table carries -- so all three scan
`analytics_events` directly and pin the finished-run condition themselves.

Two answers are decided here rather than in SQL. A database that is not
configured -- and no caller-owned connection to fall back on -- yields an empty
list rather than an error, because "not wired up yet" is a page state and not a
failure. And a selection that excludes `agent_exit` leaves every one of these
scans nothing to match, since each pins that event itself, so all three return
without dialing rather than running a query whose two conditions contradict.
The two capped reads pass a non-positive cap straight through, where it means
"every cell" rather than "no rows".
"""

from __future__ import annotations

from typing import Any

from orchestrator.observability.analytics.query.conditions import agent_event_excluded
from orchestrator.observability.analytics.query.requests import (
    FILTERED_READ_SIGNATURE,
    LIMITED_READ_SIGNATURE,
    bind_read_request,
    resolve_read_query,
    window_filters,
)
from orchestrator.observability.analytics.query.skill_adoption import skill_adoption_rows
from orchestrator.observability.analytics.query.skill_matrices import (
    skill_trigger_matrix_rows,
)
from orchestrator.observability.analytics.query.skill_models import (
    SkillAdoptionRow,
    SkillTriggerMatrixRow,
    SkillTriggerRateRow,
)
from orchestrator.observability.analytics.query.skill_trigger_rates import (
    skill_trigger_rate_rows,
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
    return skill_trigger_rate_rows(query, window_filters(request))


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
    return skill_trigger_matrix_rows(
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
    return skill_adoption_rows(
        query,
        window_filters(request),
        selected_limit,
    )


get_skill_adoption.__signature__ = _SKILL_ADOPTION_SIGNATURE
