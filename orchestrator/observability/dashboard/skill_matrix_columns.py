# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The seven columns the invocation-level trigger matrix is read across.

A column is its key, its heading, its alignment, and the reading a row is
ordered by when an operator clicks it, declared as one object so a header
cannot offer a sort the ordering does not know how to run. The four naming
columns are ordered case-insensitively, because a repository or skill an
operator reads as one name should not split into two runs of rows over how the
sink happened to capitalize it, and the three counts are ordered as numbers so
`10` lands above `9` rather than beside `1`. Which of them are numbers is
declared beside the columns rather than inferred, since it is also what decides
the direction a first click on a header means.

The two query parameters those headers write are settled here too: a sort
survives a page rerun only while the link that writes it and the parse that
reads it back spell it the same way. Both are prefixed rather than bare so the
adoption matrix above this one can carry its own selection in the same URL
without either table reordering the other.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable

from orchestrator.observability.analytics.query.skill_models import (
    SkillTriggerMatrixRow,
)


@dataclass(frozen=True)
class SkillMatrixColumn:
    key: str
    label: str
    right_aligned: bool
    sort_value: Callable[[SkillTriggerMatrixRow], object]


SKILL_MATRIX_COLUMNS = (
    SkillMatrixColumn("repo", "Repo", False, lambda row: (row.repo or "").lower()),
    SkillMatrixColumn("role", "Role", False, lambda row: (row.agent_role or "").lower()),
    SkillMatrixColumn("backend", "Backend", False, lambda row: (row.backend or "").lower()),
    SkillMatrixColumn("skill", "Skill", False, lambda row: (row.skill or "").lower()),
    SkillMatrixColumn("runs", "Runs", True, lambda row: int(row.runs)),
    SkillMatrixColumn("skill_runs", "Runs with skill", True, lambda row: int(row.skill_runs)),
    SkillMatrixColumn("rate", "Trigger rate", True, lambda row: row.rate),
)
SKILL_MATRIX_NUMERIC_KEYS = frozenset(("runs", "skill_runs", "rate"))
SKILL_MATRIX_SORT_KEYS = MappingProxyType(
    {column.key: column.sort_value for column in SKILL_MATRIX_COLUMNS},
)
SKILL_MATRIX_SORT_PARAM = "mtx_sort"
SKILL_MATRIX_DIR_PARAM = "mtx_dir"
