# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The card a window's skill adoption is reported in, and what folds under it.

The card leads with the per-session adoption table because that is the page's
primary skill metric, and folds the two invocation-level views into a collapsed
expander beneath it, so a per-run diagnostic cannot be read as the headline. One
notice covers the whole card: a window with no `agent_exit` row has nothing for
either view to report, so it is rendered once and the card returns rather than
leaving each table to draw an empty state of its own.

The caption under the adoption table is the reading decided here, and it exists
to keep the page from recommending a switch that is already on. A present row is
itself evidence that something was recorded, so a window whose cells are all
zero is a genuine 0% rather than missing tracking, and the caption says so --
naming whichever evidence the window actually carries, so an operator can match
it against the counts in the columns above. A window with no cells at all
captions nothing, because the table itself already renders the notice naming the
opt-in switch and saying it twice would read as two separate problems.

Whether the window carried any adoption evidence is what the expander beneath is
handed, since the same question is asked one level down: a window where no run
triggered a skill is a genuine no-trigger once tracking is confirmed on, and a
prompt to turn it on otherwise.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from orchestrator.observability.analytics.query.skill_models import (
    SkillAdoptionRow,
    SkillTriggerMatrixRow,
    SkillTriggerRateRow,
)
from orchestrator.observability.dashboard.card_html import card_header_html
from orchestrator.observability.dashboard.skill_adoption import (
    skill_adoption_html,
)
from orchestrator.observability.dashboard.skill_adoption_sort import (
    parse_skill_adoption_sort,
)
from orchestrator.observability.dashboard.skill_matrix import skill_matrix_html
from orchestrator.observability.dashboard.skill_matrix_sort import (
    parse_skill_matrix_sort,
)
from orchestrator.observability.dashboard.skill_trigger_table import (
    skill_triggers_html,
)


def render_skill_adoption(
    *,
    st: Any,
    skill_adoption_rows: Sequence[SkillAdoptionRow],
    skill_rows: Sequence[SkillTriggerRateRow],
    skill_matrix_rows: Sequence[SkillTriggerMatrixRow],
) -> None:
    """Render session adoption and invocation diagnostics."""
    with st.container(border=True):
        st.markdown(
            card_header_html(
                "Skill adoption",
                "Share of agent sessions that loaded each available skill, "
                "by repo, role, and backend (requires TRACK_SKILL_TRIGGERS)",
            ),
            unsafe_allow_html=True,
        )
        if not skill_rows:
            st.info("No `agent_exit` rows match the current filters.")
            return
        adopt_sort_key, adopt_sort_desc = parse_skill_adoption_sort(
            st.query_params
        )
        st.markdown(
            skill_adoption_html(
                skill_adoption_rows,
                sort_key=adopt_sort_key,
                descending=adopt_sort_desc,
            ),
            unsafe_allow_html=True,
        )
        caption = skill_adoption_zero_caption(skill_adoption_rows)
        if caption is not None:
            st.caption(caption)
        render_skill_invocation_diagnostics(
            st=st,
            skill_rows=skill_rows,
            skill_matrix_rows=skill_matrix_rows,
            tracking_confirmed=bool(skill_adoption_rows),
        )


def skill_adoption_zero_caption(
    skill_adoption_rows: Sequence[SkillAdoptionRow],
) -> Optional[str]:
    """Return a neutral caption for a genuine zero-adoption window."""
    if not skill_adoption_rows:
        return None
    if any(row.adopted for row in skill_adoption_rows):
        return None
    if any(row.sessions for row in skill_adoption_rows):
        return (
            "Skills were available to sessions this window but none loaded "
            "one -- a genuine 0% adoption, not missing tracking."
        )
    return skill_adoption_evidence_caption(skill_adoption_rows)


def skill_adoption_evidence_caption(
    skill_adoption_rows: Sequence[SkillAdoptionRow],
) -> str:
    """Name the evidence a window with no reported availability carries."""
    loaded = any(row.load_rows for row in skill_adoption_rows)
    incidental = any(row.incidental for row in skill_adoption_rows)
    if loaded and incidental:
        return (
            "Skills were loaded and referenced incidentally this window, but "
            "no session reported one available to adopt."
        )
    if loaded:
        return (
            "Skills were loaded this window, but no session reported one "
            "available to adopt."
        )
    return (
        "Only incidental skill references were recorded this window; no "
        "session reported a skill available to adopt."
    )


def render_skill_invocation_diagnostics(
    *,
    st: Any,
    skill_rows: Sequence[SkillTriggerRateRow],
    skill_matrix_rows: Sequence[SkillTriggerMatrixRow],
    tracking_confirmed: bool = False,
) -> None:
    """Render per-run skill diagnostics in a collapsed expander."""
    with st.expander(
        "Invocation-level diagnostics · per-run skill triggers",
        expanded=False,
    ):
        st.markdown(skill_triggers_html(skill_rows), unsafe_allow_html=True)
        if not any(row.skill_runs for row in skill_rows):
            if tracking_confirmed:
                st.caption("No agent run triggered a skill in this window.")
            else:
                st.caption(
                    "No skill triggers recorded in this window. Enable "
                    "`TRACK_SKILL_TRIGGERS` (default off) so "
                    "`record_agent_exit` records which skills each run pulls."
                )
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
