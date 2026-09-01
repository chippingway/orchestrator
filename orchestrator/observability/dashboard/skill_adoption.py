# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How many sessions loaded each skill they were offered, in one sortable table.

This is the page's primary skill metric, counted per logical agent session
rather than per run, so a session that reached for one skill a dozen times
still counts once and a talkative run cannot outweigh a quiet one. A window
with no cell at all is the one window not worth a table: it renders the notice
instead, and the message names the opt-in switch, because a quiet panel on a
page opened to find out what ran would otherwise read as a bug rather than as
tracking nobody turned on. A caller drawing one slice of a window's cells names
its own message in that slot, since a slice the window simply has none of is no
evidence about the switch and must not be answered as though it were. A window
that produced cells always renders the table, however quiet they are, since an
offered-but-never-loaded skill is the finding rather than a row to drop.

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
from typing import Sequence

from orchestrator.observability.analytics.query.skill_models import (
    SkillAdoptionRow,
)
from orchestrator.observability.dashboard.skill_adoption_headers import (
    skill_adoption_header_html,
)
from orchestrator.observability.dashboard.skill_adoption_rows import (
    skill_adoption_row_html,
)
from orchestrator.observability.dashboard.skill_adoption_sort import (
    default_sort_skill_adoption_rows,
    sort_skill_adoption_rows,
)
from orchestrator.observability.dashboard.tables import table_css, table_html


SKILL_ADOPTION_EMPTY_MESSAGE = (
    "No per-session skill adoption for this window. The table counts, per "
    "logical agent session, how many had each skill available and how many "
    "loaded it; it fills in once `TRACK_SKILL_TRIGGERS` (default off) has "
    "recorded at least one session's available and loaded skills."
)
SKILL_ADOPTION_EXTRA_CSS = """
  .orch-skilladopt td.strong { font-weight: 600; color: var(--orch-ink); }
  .orch-skilladopt-zero { color: var(--orch-muted-soft); }
  .orch-skilladopt thead th a.orch-skilladopt-h { color: inherit;
    text-decoration: none; cursor: pointer; }
  .orch-skilladopt thead th a.orch-skilladopt-h:hover {
    color: var(--orch-ink); text-decoration: underline; }
  .orch-skilladopt-sort { margin-left: 3px; color: var(--orch-accent); }
"""


def skill_adoption_html(
    rows: Sequence[SkillAdoptionRow],
    *,
    sort_key: str | None = None,
    descending: bool = False,
    empty_message: str = SKILL_ADOPTION_EMPTY_MESSAGE,
) -> str:
    """Render the per-skill session-adoption matrix to inline HTML."""
    if len(rows) == 0:
        return (
            '<div class="orch-skilladopt-empty" '
            'style="color:var(--orch-muted);font-size:12.5px;padding:8px 2px">'
            f"{html.escape(empty_message)}</div>"
        )
    if sort_key is None:
        rows = default_sort_skill_adoption_rows(rows)
    else:
        rows = sort_skill_adoption_rows(rows, sort_key, descending)
    return table_html(
        table_class="orch-skilladopt",
        css=table_css("orch-skilladopt", extra_rules=SKILL_ADOPTION_EXTRA_CSS),
        head=skill_adoption_header_html(sort_key, descending),
        rows=[skill_adoption_row_html(row) for row in rows],
    )
