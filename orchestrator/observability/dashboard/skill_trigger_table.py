# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How often each cohort of runs reached for a skill, in one table.

The panel is inline HTML rather than `st.dataframe` because its middle column
is not text: a rate is drawn twice, as a percentage and as a bar beside it, and
that bar is a share of the busiest cohort in this table rather than of every
run in the window. A window where every cohort is quiet still reads as a
comparison that way rather than as a row of stubs, and a window where none of
them triggered anything has no busiest cohort to be a share of, so the ranking
divides by one and every bar renders empty rather than the panel raising on a
page opened to find out that nothing was tracked.

A cohort the sink recorded no role or backend for is labelled `unknown` rather
than left blank, matching the bucket the read groups a NULL under, because a
category this panel drops is one an operator would read as never having run.
The percentage is rounded to whole points, since the column is compared down
the table rather than read off a single row.

Every reading a cell is built from, and the stylesheet, header, and body it is
assembled into, are the shared table's, so what is decided here is the six
columns, the bar a rate is drawn as, and the label a missing category reads.
The role and backend naming a row arrive off the sink rather than out of this
repository, so both are escaped into the markup a browser is asked to
interpret.
"""
from __future__ import annotations

import html
from collections.abc import Sequence

from orchestrator.observability.analytics.query.skill_models import (
    SkillTriggerRateRow,
)
from orchestrator.observability.dashboard.tables import (
    relative_width_pct,
    table_css,
    table_head_html,
    table_html,
)


UNKNOWN = "unknown"
SKILL_TRIGGERS_TABLE_COLUMNS = (
    ("Role", False),
    ("Backend", False),
    ("Runs", True),
    ("Skill runs", True),
    ("Trigger rate", True),
    ("Triggers", True),
)
SKILL_TRIGGERS_EXTRA_CSS = """
  .orch-skills td.strong { font-weight: 600; color: var(--orch-ink); }
  .orch-skill-rate { display: flex; align-items: center; gap: 8px;
    justify-content: flex-end; }
  .orch-skill-bar { display: block; height: 4px; width: 64px;
    border-radius: 2px; background: var(--orch-grid); overflow: hidden; }
  .orch-skill-bar > span { display: block; height: 100%;
    background: var(--orch-accent); border-radius: 2px; }
  .orch-skill-pct { min-width: 34px; color: var(--orch-ink); }
"""


def skill_trigger_row_html(
    row: SkillTriggerRateRow,
    *,
    max_rate: float,
) -> str:
    """Render one cohort as a row, its bar sized against the busiest rate."""
    role = row.agent_role or UNKNOWN
    backend = row.backend or UNKNOWN
    rate_percentage = row.rate * 100
    bar_percentage = relative_width_pct(row.rate, max_rate)
    return (
        "<tr>"
        f'<td class="strong">{html.escape(role)}</td>'
        f"<td>{html.escape(backend)}</td>"
        f'<td class="r">{int(row.runs)}</td>'
        f'<td class="r">{int(row.skill_runs)}</td>'
        '<td class="r"><span class="orch-skill-rate">'
        '<span class="orch-skill-bar">'
        f'<span style="width:{bar_percentage:.1f}%"></span></span>'
        f'<span class="orch-skill-pct">{rate_percentage:.0f}%</span>'
        "</span></td>"
        f'<td class="r">{int(row.total_triggers)}</td></tr>'
    )


def skill_triggers_html(rows: Sequence[SkillTriggerRateRow]) -> str:
    """Render aggregate skill-trigger rates to inline HTML."""
    max_rate = max((row.rate for row in rows), default=0) or 1.0
    return table_html(
        table_class="orch-skills",
        css=table_css(
            "orch-skills",
            extra_rules=SKILL_TRIGGERS_EXTRA_CSS,
        ),
        head=table_head_html(SKILL_TRIGGERS_TABLE_COLUMNS),
        rows=[
            skill_trigger_row_html(row, max_rate=max_rate)
            for row in rows
        ],
    )
