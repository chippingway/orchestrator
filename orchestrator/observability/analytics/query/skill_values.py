# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The cohort a skill cell is filed under, and the payload it is read from.

A skill fact is not a column. It rides in the `extras` JSONB blob of an
`agent_exit` row, so every reader here starts from a value a driver may hand
back three ways -- an adapted Python list, the raw JSON text, or nothing at all
because the key was never written. All three collapse to a list of names, and a
malformed blob collapses to an empty one rather than raising, because one bad
`extras` payload must not take a whole window's aggregate down with it.

The cohort is the other half. Every skill read groups by the same
`(repo, agent_role, backend)` triple, with a missing role or backend reading as
`unknown` rather than being dropped -- a run that recorded neither is still a
run the cohort's denominator counts. The key types name that triple and the
two four-part keys built from it, so a projection reads the shape it is
accumulating under rather than a bare tuple.

The matrix ordering lives here for the same reason: it ranks by counts the
caller passes in, so it belongs beside the cohort it sorts on rather than
inside either aggregate that asks for it.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

# One cohort, and the two cells keyed by a skill name inside it. The matrix and
# the adoption key have the same shape and are named apart because what a cell
# counts differs: triggered runs on one side, adopting sessions on the other.
SkillCohort = tuple[str, str, str]
SkillMatrixKey = tuple[str, str, str, str]
SkillAdoptionKey = tuple[str, str, str, str]


def as_skill_names(raw: Any) -> list[str]:
    """Coerce a JSONB skill-name array column into a list of strings.

    psycopg adapts a `jsonb` array to a Python list, so the common path
    is a passthrough; a driver / fixture that hands back the raw JSON
    text is tolerated too. ``None`` (the absent-key result of
    ``extras -> 'skills_...'``), a non-list payload, or a non-string
    element collapses to an empty list / is skipped so a malformed
    `extras` blob never raises mid-read.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return []
    if not isinstance(raw, (list, tuple)):
        return []
    return [name for name in raw if isinstance(name, str)]


def label_or_unknown(raw: Any) -> str:
    """Read one grouping label, bucketing an unrecorded one under `unknown`."""
    if raw is None:
        return "unknown"
    return str(raw)


def row_label(row: Sequence[Any], index: int) -> str:
    """Read a grouping label a narrower row may not carry at all."""
    if len(row) <= index:
        return "unknown"
    return label_or_unknown(row[index])


def skill_matrix_order_key(
    key: SkillMatrixKey,
    *,
    counts: dict[SkillMatrixKey, int],
    cohort_runs: dict[SkillCohort, int],
) -> list:
    """Lexicographic sort key: most-run cohorts first, then name order."""
    repo, role, backend, skill = key
    return [
        -counts.get(key, 0),
        -cohort_runs.get((repo, role, backend), 0),
        repo,
        role,
        backend,
        skill,
    ]


def skill_cohort(row: Sequence[Any]) -> SkillCohort:
    """Normalize one row's repository, role, and backend cohort."""
    return (
        label_or_unknown(row[0]),
        row_label(row, 1),
        row_label(row, 2),
    )
