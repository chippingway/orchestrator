# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The order a whole page is drawn in, and the two reads it stops short on.

This is where the other drawing owners are composed: the topbar first, because
it is the one section a page with nothing behind it still shows; then the
headline tiles over what the filters kept; then the two surfaces an operator
narrows down to one run through; then the receipt under them.

Two of those steps are returns rather than sections, and they are worded apart
because they are different facts. A file that held no records at all stops at
the empty-file notice, which names the file it read -- a strip of zeroes above
an empty table would read as "nothing ran" when the answer is "nothing was ever
written here". A read the filters then emptied stops after the tiles, because
the counts above it are what tell an operator that their own narrowing is what
dropped the runs.

The footer is the page's receipt: how many runs are on screen out of how many
the file held, and the path they came from. The path is escaped before it
reaches the markup, because it is operator-supplied text written out with
``unsafe_allow_html=True``.

Streamlit is the caller's, handed in rather than imported, so this owner stays
loadable in an install carrying no viewer dependencies at all.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from typing import Any

from orchestrator.observability.dashboard import formatting
from orchestrator.observability.trajectory_viewer import (
    page_models,
    page_setup,
    picker,
    summaries,
    summary_html,
)
from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun


def render_trajectory_footer(
    st: Any,
    shown_count: int,
    page: page_models._TrajectoryPage,
) -> None:
    """Say how much of the read is on screen, and which file it came from."""
    st.markdown(
        '<div class="orch-foot">'
        f"{formatting.fmt_num(shown_count)} of "
        f"{formatting.fmt_num(page.total)} recorded "
        f"trajectories · reading {html.escape(str(page.log_path))}</div>",
        unsafe_allow_html=True,
    )


def render_trajectory_page(
    st: Any,
    page: page_models._TrajectoryPage,
    filters: page_models._TrajectoryFilters,
    shown: Sequence[TrajectoryRun],
) -> None:
    """Draw one read, stopping at whichever empty state it reached."""
    st.markdown(
        summary_html.topbar_html(page.total, len(shown)),
        unsafe_allow_html=True,
    )
    if page.total == 0:
        picker.render_no_trajectories(st, page.log_path)
        return
    st.markdown(
        summary_html.kpi_strip_html(summaries.summarize(shown)),
        unsafe_allow_html=True,
    )
    if not shown:
        st.info(page_setup.EMPTY_FILTER_MESSAGE)
        return
    picker.render_run_list(
        st,
        shown,
        page.fixture_total,
        filters.hide_fixtures,
    )
    picker.render_run_picker(st, shown)
    render_trajectory_footer(st, len(shown), page)
