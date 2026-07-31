# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which of a repository's offered skills each cohort actually triggered.

Two scans, because the answer needs a universe as well as observations. The
runs scan says what fired; the catalog scan says what was on offer, and without
it a skill nobody triggered has no row at all -- which reads as "not applicable
here" when the point is that it was available and went unused. Padding the
observed cells with the catalog is what turns absence into an explicit zero.

The two scans are filtered differently on purpose. A `repo_skill_catalog`
record is a repository-level fact -- no issue, no stage, and written whenever
the catalog was last scanned -- so pushing the window, issue, or stage
selection onto it would drop every catalog row and silently collapse the
padding. The runs scan takes the full selection minus the caller's event
filter, which the finished-run condition replaces.

Padding is per cohort, not per repository: every cohort that ran gets the
repository's catalog skills, so a decomposer or question cohort that triggers
nothing still reports its zeros against its own run count. A skill that fired
but is not in the catalog keeps its observed cell -- what ran is not discarded
for disagreeing with what was offered -- it simply gets no zeros elsewhere.
Ordering puts the most-triggered cells first, then the busiest cohort, then the
name tiebreak, so the cap keeps the rows a reader would have looked at first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from orchestrator.observability.analytics.query.conditions import (
    AGENT_EXIT_CONDITION,
    append_where_condition,
)
from orchestrator.observability.analytics.query.execution import ReadQuery
from orchestrator.observability.analytics.query.filters import WindowFilters
from orchestrator.observability.analytics.query.predicates import build_window_where
from orchestrator.observability.analytics.query.row_cells import row_value
from orchestrator.observability.analytics.query.skill_models import SkillTriggerMatrixRow
from orchestrator.observability.analytics.query.skill_values import (
    SkillCohort,
    SkillMatrixKey,
    as_skill_names,
    skill_cohort,
    skill_matrix_order_key,
)

SKILL_MATRIX_ROW_LIMIT = 100


def skill_catalog_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[tuple]:
    """Scan the repository-level catalog records the padding is drawn from."""
    catalog_where, catalog_bindings = build_window_where(filters.catalog_scope())
    clause = append_where_condition(
        catalog_where,
        "event = 'repo_skill_catalog'",
    )
    return query.select(
        f"SELECT repo, extras -> 'skills_available' AS skills_available FROM analytics_events{clause}",
        catalog_bindings,
    )


def skill_catalog(rows: Sequence[tuple]) -> dict[str, set[str]]:
    """Union every catalog record a repository reported into one offered set."""
    catalog: dict[str, set[str]] = {}
    for row in rows:
        if row[0] is None:
            continue
        repo = str(row[0])
        names = as_skill_names(row_value(row, 1, None))
        catalog.setdefault(repo, set()).update(names)
    return catalog


def skill_run_rows(
    query: ReadQuery,
    filters: WindowFilters,
) -> list[tuple]:
    """Scan the window's finished runs and the skills each one triggered."""
    run_where, run_bindings = build_window_where(filters.without_events())
    clause = append_where_condition(run_where, AGENT_EXIT_CONDITION)
    return query.select(
        "SELECT repo, "
        "COALESCE(agent_role, 'unknown') AS role_label, "
        "COALESCE(backend, 'unknown') AS backend_label, "
        "extras -> 'skills_triggered' AS skills_triggered "
        f"FROM analytics_events{clause}",
        run_bindings,
    )


@dataclass
class SkillMatrixCounts:
    """Run and trigger counts used to assemble the skill matrix."""

    cohort_runs: dict[SkillCohort, int] = field(default_factory=dict)
    skill_runs: dict[SkillMatrixKey, int] = field(default_factory=dict)

    @classmethod
    def from_rows(cls, rows: Sequence[tuple]) -> SkillMatrixCounts:
        counts = cls()
        for row in rows:
            cohort = skill_cohort(row)
            counts.cohort_runs[cohort] = counts.cohort_runs.get(cohort, 0) + 1
            for skill in set(as_skill_names(row_value(row, 3, None))):
                key = (*cohort, skill)
                counts.skill_runs[key] = counts.skill_runs.get(key, 0) + 1
        return counts

    def matrix_keys(
        self,
        catalog: dict[str, set[str]],
    ) -> set[SkillMatrixKey]:
        keys = set(self.skill_runs)
        for cohort in self.cohort_runs:
            for skill in catalog.get(cohort[0], ()):
                keys.add((*cohort, skill))
        return keys

    def order_key(self, key: SkillMatrixKey) -> list:
        return skill_matrix_order_key(
            key,
            counts=self.skill_runs,
            cohort_runs=self.cohort_runs,
        )

    def as_row(self, key: SkillMatrixKey) -> SkillTriggerMatrixRow:
        repo, role, backend, skill = key
        return SkillTriggerMatrixRow(
            repo=repo,
            skill=skill,
            agent_role=role,
            backend=backend,
            runs=self.cohort_runs.get((repo, role, backend), 0),
            skill_runs=self.skill_runs.get(key, 0),
        )


def skill_trigger_matrix_rows(
    query: ReadQuery,
    filters: WindowFilters,
    limit: int,
) -> list[SkillTriggerMatrixRow]:
    """Return the observed and catalog-padded cells, ranked and capped."""
    catalog = skill_catalog(skill_catalog_rows(query, filters))
    counts = SkillMatrixCounts.from_rows(skill_run_rows(query, filters))
    keys = sorted(counts.matrix_keys(catalog), key=counts.order_key)
    if limit > 0:
        keys = keys[:limit]
    return [counts.as_row(key) for key in keys]
