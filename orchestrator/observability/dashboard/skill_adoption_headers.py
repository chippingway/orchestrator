# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The adoption table's header row, where every column is also its sort control.

Streamlit's own table cannot draw a header that re-sorts a hand-rolled panel,
so each heading is an anchor writing the pair of query parameters the parse
reads back. The link targets the current tab, because a sort that opened a
second copy of the page would lose the filters the table was narrowed by.

What a click means depends on where the column already stands. The active one
offers the opposite of what it is showing, so clicking it again reverses the
table rather than re-applying the same order, and it is the only column drawn
with an arrow -- an indicator on every heading would say nothing about which
one the rows are actually in. An inactive column offers descending when it
counts and ascending when it names, because the interesting end of a count is
the busiest row while the interesting end of a name is the top of the alphabet.

A heading is escaped into the markup like every other value the panel writes,
even though the vocabulary it comes from is this repository's own.
"""
from __future__ import annotations

import html
from dataclasses import dataclass

from orchestrator.observability.dashboard.skill_adoption_columns import (
    SKILL_ADOPTION_COLUMNS,
    SKILL_ADOPTION_DIR_PARAM,
    SKILL_ADOPTION_NUMERIC_KEYS,
    SKILL_ADOPTION_SORT_PARAM,
    SkillAdoptionColumn,
)


@dataclass(frozen=True)
class SkillAdoptionHeaderState:
    direction: str
    arrow: str


def skill_adoption_header_state(
    column: SkillAdoptionColumn,
    active_key: str | None,
    descending: bool,
) -> SkillAdoptionHeaderState:
    """What a click on one heading offers, and the arrow it carries."""
    if column.key == active_key:
        direction = "asc" if descending else "desc"
        arrow = "▼" if descending else "▲"
        return SkillAdoptionHeaderState(direction=direction, arrow=arrow)
    if column.key in SKILL_ADOPTION_NUMERIC_KEYS:
        return SkillAdoptionHeaderState(direction="desc", arrow="")
    return SkillAdoptionHeaderState(direction="asc", arrow="")


def skill_adoption_header_cell(
    column: SkillAdoptionColumn,
    active_key: str | None,
    descending: bool,
) -> str:
    """Draw one heading as the link that writes its selection."""
    state = skill_adoption_header_state(column, active_key, descending)
    cell_class = ' class="r"' if column.right_aligned else ""
    arrow_html = ""
    if state.arrow:
        arrow_html = f'<span class="orch-skilladopt-sort">{state.arrow}</span>'
    return (
        f"<th{cell_class}>"
        '<a class="orch-skilladopt-h" '
        f'href="?{SKILL_ADOPTION_SORT_PARAM}={column.key}'
        f'&{SKILL_ADOPTION_DIR_PARAM}={state.direction}" target="_self">'
        f"{html.escape(column.label)}</a>{arrow_html}</th>"
    )


def skill_adoption_header_html(
    active_key: str | None,
    descending: bool,
) -> str:
    """Assemble the header row the table's sorts are clicked from."""
    cells = (
        skill_adoption_header_cell(column, active_key, descending)
        for column in SKILL_ADOPTION_COLUMNS
    )
    return "<thead><tr>{0}</tr></thead>".format("".join(cells))
