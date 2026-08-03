# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The trigger-rate card the page's skill section used to lead with.

The per-session adoption card is what the page draws now, so nothing in the
render pipeline reaches this one; it stays for a caller that names it, and it
stays whole rather than reduced to the table beneath it because a card is what
such a caller asked for -- the header, the single notice a window with no
`agent_exit` row is answered with, the aggregate rates, the prompt to enable
tracking when no run triggered anything, and the per-skill matrix folded into a
collapsed expander under all of it.

The prompt here is unconditional where the adoption card's is not, because a
window of trigger rates carries no per-session evidence to tell a genuine
no-trigger apart from tracking nobody turned on.
"""
from __future__ import annotations

from typing import Any, Sequence

from orchestrator.observability.analytics.query.skill_models import (
    SkillTriggerMatrixRow,
    SkillTriggerRateRow,
)
from orchestrator.observability.dashboard.card_html import card_header_html
from orchestrator.observability.dashboard.skill_matrix import skill_matrix_html
from orchestrator.observability.dashboard.skill_matrix_sort import (
    parse_skill_matrix_sort,
)
from orchestrator.observability.dashboard.skill_trigger_table import (
    skill_triggers_html,
)

NO_AGENT_EXITS_MESSAGE = "No `agent_exit` rows match the current filters."


def render_skill_triggers(
    *,
    st: Any,
    skill_rows: Sequence[SkillTriggerRateRow],
    skill_matrix_rows: Sequence[SkillTriggerMatrixRow],
) -> None:
    """Render the compatibility trigger-rate skill panel."""
    with st.container(border=True):
        st.markdown(
            card_header_html(
                "Skill trigger rates",
                "Share of agent runs that triggered a skill, by role and "
                "backend (requires TRACK_SKILL_TRIGGERS)",
            ),
            unsafe_allow_html=True,
        )
        if not skill_rows:
            st.info(NO_AGENT_EXITS_MESSAGE)
            return
        st.markdown(skill_triggers_html(skill_rows), unsafe_allow_html=True)
        if not any(row.skill_runs for row in skill_rows):
            st.caption(
                "No skill triggers recorded in this window. Enable "
                "`TRACK_SKILL_TRIGGERS` (default off) so "
                "`record_agent_exit` records which skills each run pulls."
            )
        render_skill_matrix_expander(
            st=st,
            skill_matrix_rows=skill_matrix_rows,
        )


def render_skill_matrix_expander(
    *,
    st: Any,
    skill_matrix_rows: Sequence[SkillTriggerMatrixRow],
) -> None:
    """Render the per-skill trigger matrix in a collapsed expander."""
    with st.expander(
        "Per-skill trigger matrix · which skills each "
        "repo × role × backend cohort reaches for",
        expanded=False,
    ):
        matrix_sort_key, matrix_sort_desc = parse_skill_matrix_sort(
            st.query_params
        )
        st.markdown(
            skill_matrix_html(
                skill_matrix_rows,
                sort_key=matrix_sort_key,
                descending=matrix_sort_desc,
            ),
            unsafe_allow_html=True,
        )
