# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one cell of the trigger matrix says, and how it is drawn.

A cell pairs one `(repo, role, backend, skill, level)` cohort with how many of
its runs reached for that skill, and the reason the panel exists is the cohort
that reached for it on none of them: the skill is in the repository's catalog
and the cohort ran, so an explicit zero is the answer an operator came for.
That zero is toned down rather than dropped, and its derived rate is toned with
it, so a row an operator is scanning past reads as quiet in both columns at
once while the cohort's own run total stays a plain number -- it is the
denominator the zero is read against, not part of the finding.

The rate is rounded to whole points, since the column is compared down the
table rather than read off a single row. The level beside the skill names the
source a definition came from, so a catalog-padded cell and a run that
triggered the same name under no recorded level stay legible as the two
definitions they are. A category the sink recorded nothing for -- including a
level no record classified -- is labelled through the same `unknown` the
aggregate panel reads a missing role or backend under, so the two tables bucket
an empty category the same way.

Every naming column arrives off the sink rather than out of this repository, so
all five are escaped into the markup a browser is asked to interpret.
"""
from __future__ import annotations

import html
from dataclasses import dataclass

from orchestrator.observability.analytics.query.skill_models import (
    SkillTriggerMatrixRow,
)
from orchestrator.observability.dashboard.skill_trigger_table import UNKNOWN


def muted_zero_html(text: str) -> str:
    """The tone a quiet cell's count and rate are both drawn in."""
    return f'<span class="orch-skillmatrix-zero">{text}</span>'


@dataclass(frozen=True)
class SkillMatrixRowView:
    repo: str
    role: str
    backend: str
    skill: str
    level: str
    runs: int
    skill_runs_html: str
    rate_html: str


def skill_matrix_row_view(row: SkillTriggerMatrixRow) -> SkillMatrixRowView:
    """Reduce one cell to the readings its eight columns are drawn from."""
    skill_runs = int(row.skill_runs)
    if skill_runs == 0:
        skill_runs_html = muted_zero_html("0")
        rate_html = muted_zero_html("0%")
    else:
        skill_runs_html = str(skill_runs)
        rate_percentage = row.rate * 100
        rate_html = f"{rate_percentage:.0f}%"
    return SkillMatrixRowView(
        repo=row.repo or UNKNOWN,
        role=row.agent_role or UNKNOWN,
        backend=row.backend or UNKNOWN,
        skill=row.skill or UNKNOWN,
        level=row.level or UNKNOWN,
        runs=int(row.runs),
        skill_runs_html=skill_runs_html,
        rate_html=rate_html,
    )


def skill_matrix_row_html(row: SkillTriggerMatrixRow) -> str:
    """Render one cell as a row of the matrix."""
    row_view = skill_matrix_row_view(row)
    return (
        "<tr>"
        f'<td class="strong">{html.escape(row_view.repo)}</td>'
        f"<td>{html.escape(row_view.role)}</td>"
        f"<td>{html.escape(row_view.backend)}</td>"
        f"<td>{html.escape(row_view.skill)}</td>"
        f"<td>{html.escape(row_view.level)}</td>"
        f'<td class="r">{row_view.runs}</td>'
        f'<td class="r">{row_view.skill_runs_html}</td>'
        f'<td class="r">{row_view.rate_html}</td>'
        "</tr>"
    )
