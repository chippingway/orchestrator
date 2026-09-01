# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which skills each repository's runs reached for, in one sortable table.

The panel pairs a repository's offered-skill catalog with the skills its runs
actually triggered, so it has two ways of being empty and only one of them is
worth a table. A window that produced no cells at all has no catalog to pair
anything with, so it renders the notice instead: the message names the opt-in
switch, because a quiet panel on a page opened to find out what ran would
otherwise read as a bug rather than as tracking nobody turned on. A window that
produced cells always renders the table, however quiet the cells are, since an
offered-but-never-triggered skill is the finding rather than a row to drop.

The rows arrive in whatever order the read handed them back, so this is where
an order is decided: the clicked column when the page URL named one, and the
repository-then-rate default when it did not. Ordering here rather than in the
read is what lets a click re-sort the table without reissuing the query behind
it.

The stylesheet, header, and body the panel is assembled into are the shared
table's; what is added on top is the tone a quiet cell is drawn in and the
sortable heading, both scoped to this panel's own class so the tables beside it
keep their own.
"""
from __future__ import annotations

import html
from collections.abc import Sequence

from orchestrator.observability.analytics.query.skill_models import (
    SkillTriggerMatrixRow,
)
from orchestrator.observability.dashboard.skill_matrix_headers import (
    skill_matrix_header_html,
)
from orchestrator.observability.dashboard.skill_matrix_rows import (
    skill_matrix_row_html,
)
from orchestrator.observability.dashboard.skill_matrix_sort import (
    default_sort_skill_matrix_rows,
    sort_skill_matrix_rows,
)
from orchestrator.observability.dashboard.tables import table_css, table_html

SKILL_MATRIX_EMPTY_MESSAGE = (
    "No catalog-backed skill matrix for this window. The matrix pairs "
    "each repo's offered-skill catalog with the skills its runs "
    "triggered; it fills in once `TRACK_SKILL_TRIGGERS` (default off) "
    "has recorded a repo skill catalog and at least one run's triggered "
    "skills."
)
SKILL_MATRIX_EXTRA_CSS = """
  .orch-skillmatrix td.strong { font-weight: 600; color: var(--orch-ink); }
  .orch-skillmatrix-zero { color: var(--orch-muted-soft); }
  .orch-skillmatrix thead th a.orch-skillmatrix-h { color: inherit;
    text-decoration: none; cursor: pointer; }
  .orch-skillmatrix thead th a.orch-skillmatrix-h:hover {
    color: var(--orch-ink); text-decoration: underline; }
  .orch-skillmatrix-sort { margin-left: 3px; color: var(--orch-accent); }
"""


def skill_matrix_html(
    rows: Sequence[SkillTriggerMatrixRow],
    *,
    sort_key: str | None = None,
    descending: bool = False,
) -> str:
    """Render the invocation-level per-skill matrix to inline HTML."""
    if len(rows) == 0:
        return (
            '<div class="orch-skillmatrix-empty" '
            'style="color:var(--orch-muted);font-size:12.5px;padding:8px 2px">'
            f"{html.escape(SKILL_MATRIX_EMPTY_MESSAGE)}</div>"
        )
    if sort_key is None:
        rows = default_sort_skill_matrix_rows(rows)
    else:
        rows = sort_skill_matrix_rows(rows, sort_key, descending)
    return table_html(
        table_class="orch-skillmatrix",
        css=table_css("orch-skillmatrix", extra_rules=SKILL_MATRIX_EXTRA_CSS),
        head=skill_matrix_header_html(sort_key, descending),
        rows=[skill_matrix_row_html(row) for row in rows],
    )
