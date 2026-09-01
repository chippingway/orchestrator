# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The cells the invocation-level matrix cases are built out of.

Every module here spells a cell the same way, because the five naming columns
and the two counts are what each of them reads a different decision off: an
ordering case and a projection case that built their cells differently would
stop being comparable. The repositories are named apart so an assertion can
locate one row by the only cell that is unique to it.
"""

from __future__ import annotations

from dataclasses import dataclass

from orchestrator.observability.analytics.query.skill_models import (
    SkillTriggerMatrixRow,
)
from orchestrator.observability.dashboard import skill_matrix

DEVELOPER = "developer"

REVIEWER = "reviewer"

CLAUDE = "claude"

CODEX = "codex"

REPO_A = "a/repo"

REPO_B = "b/repo"

REPO_C = "c/repo"

SKILL_ALPHA = "alpha"

SKILL_BETA = "beta"

SKILL_GAMMA = "gamma"

LEVEL_PROJECT = "project"

LEVEL_USER = "user"

# A cohort that ran four times and reached for the skill on one of them, so a
# rounded rate is readable off the markup and the two counts stay distinct.
COHORT_RUNS = 4

SKILL_RUNS = 1


@dataclass(frozen=True)
class CellCase:
    repo: str = REPO_A
    skill: str = SKILL_ALPHA
    role: str = DEVELOPER
    backend: str = CLAUDE
    level: str = LEVEL_PROJECT
    runs: int = COHORT_RUNS
    skill_runs: int = SKILL_RUNS


def cell(case: CellCase) -> SkillTriggerMatrixRow:
    """One read row of the `(repo, skill, level, role, backend)` cell it names."""
    return SkillTriggerMatrixRow(
        repo=case.repo,
        skill=case.skill,
        agent_role=case.role,
        backend=case.backend,
        level=case.level,
        runs=case.runs,
        skill_runs=case.skill_runs,
    )


def cells(*cases: CellCase) -> list[SkillTriggerMatrixRow]:
    """The read rows those cases name, in the order they were given."""
    return [cell(case) for case in cases]


def rendered(
    *cases: CellCase,
    sort_key: str | None = None,
    descending: bool = False,
) -> str:
    """The matrix those cells are drawn into."""
    return skill_matrix.skill_matrix_html(
        cells(*cases),
        sort_key=sort_key,
        descending=descending,
    )


def cell_fragment(text: str) -> str:
    """The markup a naming column reports `text` in."""
    return f">{text}<"
