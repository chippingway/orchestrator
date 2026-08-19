# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The ten columns per-session skill adoption is read across.

A column is its key, its heading, its alignment, and the reading a row is
ordered by when an operator clicks it, declared as one object so a header
cannot offer a sort the ordering does not know how to run. The five naming
columns are ordered case-insensitively, because a repository or skill an
operator reads as one name should not split into two runs of rows over how the
sink happened to capitalize it, and the five counts are ordered as numbers so
`10` lands above `9` rather than beside `1`. Which of them are numbers is
declared beside the columns rather than inferred, since it is also what decides
the direction a first click on a header means.

The source level a skill was defined at is one of those naming columns rather
than a qualifier on the name beside it, because it is what separates two rows a
name alone would read as one: a repository's own `develop` and a same-named
global one are different definitions with different adoption. Ordering by it
gathers every definition from one level together, which is the reading an
operator comparing what a harness ships against what a repository checks in
sorts on.

Two of those counts are diagnostics rather than the metric: a skill some
session loaded without reporting it available, and a `SKILL.md` a run only
mentioned in passing. Both are columns of their own so neither can be read into
the rate beside them, and both are orderable like the rest, because a window's
incidental references are a finding an operator sorts to the top rather than
a footnote.

The two query parameters those headers write are settled here too: a sort
survives a page rerun only while the link that writes it and the parse that
reads it back spell it the same way. Both are prefixed rather than bare so the
invocation-level matrix above this one can carry its own selection in the same
URL without either table reordering the other.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable

from orchestrator.observability.analytics.query.skill_models import (
    SkillAdoptionRow,
)


@dataclass(frozen=True)
class SkillAdoptionColumn:
    key: str
    label: str
    right_aligned: bool
    sort_value: Callable[[SkillAdoptionRow], object]


SKILL_ADOPTION_COLUMNS = (
    SkillAdoptionColumn("repo", "Repo", False, lambda row: (row.repo or "").lower()),
    SkillAdoptionColumn("role", "Role", False, lambda row: (row.agent_role or "").lower()),
    SkillAdoptionColumn("backend", "Backend", False, lambda row: (row.backend or "").lower()),
    SkillAdoptionColumn("skill", "Skill", False, lambda row: (row.skill or "").lower()),
    SkillAdoptionColumn("level", "Level", False, lambda row: (row.level or "").lower()),
    SkillAdoptionColumn("sessions", "Sessions", True, lambda row: int(row.sessions)),
    SkillAdoptionColumn("adopted", "Sessions using skill", True, lambda row: int(row.adopted)),
    SkillAdoptionColumn("rate", "Adoption rate", True, lambda row: row.adoption_rate),
    SkillAdoptionColumn("loads", "Invocation loads", True, lambda row: int(row.load_rows)),
    SkillAdoptionColumn("incidental", "Incidental references", True, lambda row: int(row.incidental)),
)
SKILL_ADOPTION_NUMERIC_KEYS = frozenset(
    ("sessions", "adopted", "rate", "loads", "incidental"),
)
SKILL_ADOPTION_SORT_KEYS = MappingProxyType(
    {column.key: column.sort_value for column in SKILL_ADOPTION_COLUMNS},
)
SKILL_ADOPTION_SORT_PARAM = "adopt_sort"
SKILL_ADOPTION_DIR_PARAM = "adopt_dir"
