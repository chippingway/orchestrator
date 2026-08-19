# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The cells the per-session adoption cases are built out of.

Every module here spells a cell the same way, because the five naming columns
and the five counts are what each of them reads a different decision off: an
ordering case and a projection case that built their cells differently would
stop being comparable. The repositories are named apart so an assertion can
locate one row by the only cell that is unique to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from orchestrator.observability.analytics.query.skill_models import (
    SkillAdoptionRow,
)
from orchestrator.observability.dashboard import skill_adoption

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

# A cohort the skill was available to in four sessions and loaded in one, so a
# rounded rate is readable off the markup and the two counts stay distinct.
AVAILABLE_SESSIONS = 4

ADOPTED_SESSIONS = 1


@dataclass(frozen=True)
class CellCase:
    repo: str = REPO_A
    skill: str = SKILL_ALPHA
    role: str = DEVELOPER
    backend: str = CLAUDE
    level: str = LEVEL_PROJECT
    sessions: int = AVAILABLE_SESSIONS
    adopted: int = ADOPTED_SESSIONS
    load_rows: int = 0
    incidental: int = 0


def cell(case: CellCase) -> SkillAdoptionRow:
    """One read row of the `(repo, skill, level, role, backend)` cell it names."""
    return SkillAdoptionRow(
        repo=case.repo,
        skill=case.skill,
        agent_role=case.role,
        backend=case.backend,
        level=case.level,
        sessions=case.sessions,
        adopted=case.adopted,
        invocations=case.sessions,
        load_rows=case.load_rows,
        incidental=case.incidental,
    )


def cells(*cases: CellCase) -> list[SkillAdoptionRow]:
    """The read rows those cases name, in the order they were given."""
    return [cell(case) for case in cases]


def rendered(
    *cases: CellCase,
    sort_key: Optional[str] = None,
    descending: bool = False,
) -> str:
    """The table those cells are drawn into."""
    return skill_adoption.skill_adoption_html(
        cells(*cases),
        sort_key=sort_key,
        descending=descending,
    )


def cell_fragment(text: str) -> str:
    """The markup a naming column reports `text` in."""
    return f">{text}<"
