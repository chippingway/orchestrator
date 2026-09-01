# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The card one selected run is read in full through.

The order the card is written in is what it is for: identity first, then the
two notices that qualify everything under them, then the spend, then the
inventory of tools and skills, and only then the timeline -- so an operator
knows what they are reading before they read it. The fixture notice and the
truncation notice are drawn where they are for that reason: a synthetic record
and a run whose later steps the sink's budget dropped both change how the
timeline below should be read.

Two rows are always drawn where the rest are dropped when empty. The
triggered-skills row renders a ``none`` marker, because "no skill fired this
session" and "this row was omitted" are different answers to the same question.
The timeline renders a caption where a run recorded no entries at all, for the
same reason.

An entry's own body is handed to Streamlit rather than to the markup builders:
the final output is the one entry written as markdown, since it is the agent's
own prose, and everything else is a code block, because a prompt, a tool
payload, and a tool result are text that must not be interpreted. Everything
that does reach the markup is escaped by the builder that writes it.

Streamlit is the caller's, handed in rather than imported, so this owner stays
loadable in an install carrying no viewer dependencies at all.
"""

from __future__ import annotations

from typing import Any

from orchestrator.observability.trajectory_viewer.models import (
    TimelineEntry,
    TurnUsageView,
)
from orchestrator.observability.trajectory_viewer.run_html import (
    labeled_chips_html,
    meta_html,
)
from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun
from orchestrator.observability.trajectory_viewer.summary_html import card_header_html
from orchestrator.observability.trajectory_viewer.timeline_html import (
    timeline_entry_html,
    timeline_with_usage,
)
from orchestrator.observability.trajectory_viewer.usage_html import (
    run_usage_html,
    turn_usage_html,
)


def render_run_notices(st: Any, run: TrajectoryRun) -> None:
    """Draw whichever notices qualify how the rest of the card reads."""
    if run.is_fixture:
        st.info(
            "This run is flagged as a likely synthetic test fixture "
            "(a sentinel `ignored` prompt, a `sess-*` session id, or a "
            "Skill-only run). Such records can appear in a trajectory "
            "file inherited from a run with the sink enabled during the "
            "test suite."
        )
    if run.truncated:
        st.warning(
            "This trajectory was truncated by the sink's record budget; "
            "later steps were dropped before the run finished."
        )


def render_run_usage_and_chips(st: Any, run: TrajectoryRun) -> None:
    """Draw what the run cost, then the tools and skills it was offered."""
    usage_markup = run_usage_html(run)
    if usage_markup:
        st.markdown(usage_markup, unsafe_allow_html=True)
    # Skills triggered always renders (with a "none" marker when empty) so a
    # reviewer can tell "no skill fired this session" apart from an omitted
    # row. Tools offered and Skills available keep the generic empty omission.
    for label, names, empty_marker in (
        ("Tools offered", run.tools, ""),
        ("Skills triggered", run.skills_triggered, "none"),
        ("Skills available", run.skills_available, ""),
    ):
        chips = labeled_chips_html(label, names, empty_marker)
        if chips:
            st.markdown(chips, unsafe_allow_html=True)


def render_system_prompt(st: Any, run: TrajectoryRun) -> None:
    """Draw the system prompt folded away, where the record carried one."""
    if not run.system_prompt:
        return
    with st.expander("System prompt", expanded=False):
        st.code(run.system_prompt)


def render_timeline_entry(
    st: Any,
    index: int,
    strip: TurnUsageView | None,
    entry: TimelineEntry,
) -> None:
    """Draw one entry, under the usage strip where it opens a new turn."""
    if strip is not None:
        st.markdown(turn_usage_html(strip), unsafe_allow_html=True)
    st.markdown(timeline_entry_html(entry, index), unsafe_allow_html=True)
    if not entry.content:
        return
    if entry.is_output:
        st.markdown(entry.content)
    else:
        st.code(entry.content)


def render_timeline(st: Any, run: TrajectoryRun) -> None:
    """Draw the run's whole ordered sequence, or say that it recorded none."""
    st.markdown(
        '<p class="orch-card-sub" style="margin-top:14px">'
        f"Trajectory timeline · {run.step_count} steps · "
        f"{run.tool_calls} tool calls</p>",
        unsafe_allow_html=True,
    )
    if not run.timeline:
        st.caption("No timeline entries were recorded for this run.")
        return
    for index, (strip, entry) in enumerate(timeline_with_usage(run)):
        render_timeline_entry(st, index, strip, entry)


def render_run_card(st: Any, run: TrajectoryRun) -> None:
    """Draw the card's contents in the order an operator reads them."""
    st.markdown('<div class="orch-cardmark"></div>', unsafe_allow_html=True)
    repo_label = run.repo or "unknown repo"
    st.markdown(
        card_header_html(
            f"Run #{run.issue} · {repo_label}",
            "Ordered timeline: prompt, text turns, tool calls, output",
        ),
        unsafe_allow_html=True,
    )
    render_run_notices(st, run)
    st.markdown(meta_html(run), unsafe_allow_html=True)
    render_run_usage_and_chips(st, run)
    render_system_prompt(st, run)
    render_timeline(st, run)


def render_run(*, st: Any, run: TrajectoryRun) -> None:
    """Render the detail card for one selected run."""
    with st.container(border=True):
        render_run_card(st, run)
