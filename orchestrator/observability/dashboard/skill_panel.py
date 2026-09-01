# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The card a window's skill adoption is reported in, and what folds under it.

The card opens on the invocation-level views -- the per-run trigger rates and
the matrix beneath them, in one collapsed expander -- and reports per-session
adoption under them, split across one collapsed section per source level a
definition can come from. Splitting adoption that way is what keeps a
repository's own `develop` out of the same table as a same-named global one,
and folding each level on its own is what lets an operator open the level they
came to read rather than scroll one table carrying all three.

A cell no record classified gets a section of its own rather than being
dropped: a claude run names no source directory, so its loads arrive `unknown`,
and a split that knew only the three levels would quietly lose them. That
section is drawn only where such a cell exists, since it names no level an
operator can go looking for.

One notice covers the whole card: a window with no `agent_exit` row has nothing
for either view to report, so it is rendered once and the card returns rather
than leaving each table to draw an empty state of its own. A window that ran
but reported no adoption cell is answered the same way one level down -- the
adoption table's own notice is rendered once, in place of the level sections it
would otherwise be repeated in, so the opt-in switch is named once. A level
with no cell in a window that has others is a different statement and says only
that, since its emptiness is about the window's skills rather than about
tracking.

The caption beneath those sections is the reading decided here, and it exists
to keep the page from recommending a switch that is already on. A present row
is itself evidence that something was recorded, so a window whose cells are all
zero is a genuine 0% rather than missing tracking, and the caption says so --
naming whichever evidence the window actually carries, so an operator can match
it against the counts in the columns above. A window with no cells at all
captions nothing, because the table itself already renders the notice naming
the opt-in switch and saying it twice would read as two separate problems.

Whether the window carried any adoption evidence is what the diagnostics above
are handed, since the same question is asked one level down: a window where no
run triggered a skill is a genuine no-trigger once tracking is confirmed on,
and a prompt to turn it on otherwise.
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, NamedTuple

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

# The three levels a definition is filed under, in the order one shadows
# another, each with the section it is reported in. A label names the source
# rather than the level alone, since `user` and `harness` say little on their
# own about where the definition was read from.
_LEVEL_SECTIONS = (
    ("project", "Project-level skills · defined in the repository"),
    ("user", "User-level skills · installed for the operator"),
    ("harness", "Harness-level skills · built into the CLI"),
)

_UNCLASSIFIED_LABEL = "Unclassified skills · no source level recorded"

_CLASSIFIED_LEVELS = frozenset(section[0] for section in _LEVEL_SECTIONS)


class _LevelSection(NamedTuple):
    """One section the adoption cells are split across."""

    label: str
    rows: list[SkillAdoptionRow]
    empty_message: str


def render_skill_adoption(
    *,
    st: Any,
    skill_adoption_rows: Sequence[SkillAdoptionRow],
    skill_rows: Sequence[SkillTriggerRateRow],
    skill_matrix_rows: Sequence[SkillTriggerMatrixRow],
) -> None:
    """Render invocation diagnostics and per-level session adoption."""
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
        render_skill_invocation_diagnostics(
            st=st,
            skill_rows=skill_rows,
            skill_matrix_rows=skill_matrix_rows,
            tracking_confirmed=bool(skill_adoption_rows),
        )
        render_skill_adoption_levels(
            st=st,
            skill_adoption_rows=skill_adoption_rows,
        )
        caption = skill_adoption_zero_caption(skill_adoption_rows)
        if caption is not None:
            st.caption(caption)


def render_skill_adoption_levels(
    *,
    st: Any,
    skill_adoption_rows: Sequence[SkillAdoptionRow],
) -> None:
    """Draw each source level's adoption cells in a collapsed section."""
    if not skill_adoption_rows:
        st.markdown(skill_adoption_html(()), unsafe_allow_html=True)
        return
    sort_key, descending = parse_skill_adoption_sort(st.query_params)
    for section in _level_sections(skill_adoption_rows):
        with st.expander(section.label, expanded=False):
            st.markdown(
                skill_adoption_html(
                    section.rows,
                    sort_key=sort_key,
                    descending=descending,
                    empty_message=section.empty_message,
                ),
                unsafe_allow_html=True,
            )


def _level_sections(
    skill_adoption_rows: Sequence[SkillAdoptionRow],
) -> Iterator[_LevelSection]:
    """Split the cells into the sections they are reported across."""
    for level, label in _LEVEL_SECTIONS:
        yield _LevelSection(
            label,
            [row for row in skill_adoption_rows if row.level == level],
            f"No {level}-level skill was recorded in this window.",
        )
    unclassified = [
        row
        for row in skill_adoption_rows
        if row.level not in _CLASSIFIED_LEVELS
    ]
    if unclassified:
        yield _LevelSection(
            _UNCLASSIFIED_LABEL,
            unclassified,
            "No unclassified skill was recorded in this window.",
        )


def skill_adoption_zero_caption(
    skill_adoption_rows: Sequence[SkillAdoptionRow],
) -> str | None:
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
