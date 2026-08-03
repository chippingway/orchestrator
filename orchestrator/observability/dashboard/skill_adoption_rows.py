# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one cell of the adoption table says, and how it is drawn.

A cell pairs one `(repo, role, backend, skill)` cohort with how many of its
sessions had the skill available and how many loaded it, so the two ways of
being quiet are different answers and are drawn as different things. A cohort
no session had the skill available in has no denominator, so its rate is
undefined and reads as an em-dash; a cohort that was offered the skill and
loaded it in none of its sessions has a real `0%`, which is the offered-but-
ignored signal the panel exists to surface. Both are toned down rather than
dropped, as is every zero count beside them, so a row an operator is scanning
past reads as quiet without the rate claiming something the sessions do not
say.

The rate is rounded to whole points, since the column is compared down the
table rather than read off a single row. The two diagnostic counts are drawn
the same way as the session ones but stay their own columns, because a
`SKILL.md` mentioned in passing is not adoption and must never be read as it.

A category the sink recorded nothing for is labelled through the same `unknown`
the aggregate panel reads a missing role or backend under, so every table on
the page buckets an empty category the same way. All four naming columns arrive
off the sink rather than out of this repository, so all four are escaped into
the markup a browser is asked to interpret.
"""
from __future__ import annotations

import html
from dataclasses import dataclass

from orchestrator.observability.analytics.query.skill_models import (
    SkillAdoptionRow,
)
from orchestrator.observability.dashboard.skill_trigger_table import UNKNOWN


def muted_zero_html(text: str) -> str:
    """The tone a quiet count and an undefined or zero rate are drawn in."""
    return f'<span class="orch-skilladopt-zero">{text}</span>'


def adoption_count_html(count: int) -> str:
    """Draw one count, toned down when there is nothing to report."""
    if count == 0:
        return muted_zero_html("0")
    return str(count)


def adoption_rate_html(row: SkillAdoptionRow) -> str:
    """Draw the rate, distinguishing an undefined one from a real zero."""
    if row.sessions == 0:
        return muted_zero_html("—")
    if row.adopted == 0:
        return muted_zero_html("0%")
    rate_percentage = row.adoption_rate * 100
    return f"{rate_percentage:.0f}%"


@dataclass(frozen=True)
class SkillAdoptionRowView:
    repo: str
    role: str
    backend: str
    skill: str
    sessions_html: str
    adopted_html: str
    rate_html: str
    loads_html: str
    incidental_html: str


def skill_adoption_row_view(row: SkillAdoptionRow) -> SkillAdoptionRowView:
    """Reduce one cell to the readings its nine columns are drawn from."""
    return SkillAdoptionRowView(
        repo=row.repo or UNKNOWN,
        role=row.agent_role or UNKNOWN,
        backend=row.backend or UNKNOWN,
        skill=row.skill or UNKNOWN,
        sessions_html=adoption_count_html(int(row.sessions)),
        adopted_html=adoption_count_html(int(row.adopted)),
        rate_html=adoption_rate_html(row),
        loads_html=adoption_count_html(int(row.load_rows)),
        incidental_html=adoption_count_html(int(row.incidental)),
    )


def skill_adoption_row_html(row: SkillAdoptionRow) -> str:
    """Render one cell as a row of the adoption table."""
    row_view = skill_adoption_row_view(row)
    return (
        "<tr>"
        f'<td class="strong">{html.escape(row_view.repo)}</td>'
        f"<td>{html.escape(row_view.role)}</td>"
        f"<td>{html.escape(row_view.backend)}</td>"
        f"<td>{html.escape(row_view.skill)}</td>"
        f'<td class="r">{row_view.sessions_html}</td>'
        f'<td class="r">{row_view.adopted_html}</td>'
        f'<td class="r">{row_view.rate_html}</td>'
        f'<td class="r">{row_view.loads_html}</td>'
        f'<td class="r">{row_view.incidental_html}</td>'
        "</tr>"
    )
