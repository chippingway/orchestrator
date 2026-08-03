# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The bar a run of the page picks its reported window in.

One owner for the window a preset opens the bar on, the two pickers an operator
overrides it with, and the bar those are assembled into, because the three are
one round trip: what the preset resolves to is what the pickers are seeded
with, and what the pickers come back with is the window every read below is
bounded by.

The dates an operator reads and types are inclusive -- `To` is the last day the
window covers -- while the reads underneath are bounded `ts < end`. So the end
picker is seeded one day back from the half-open boundary and the pair is
handed to ``windows.to_window``, which puts that day back. Both pickers are
clamped to the recorded extent, because a window reaching past what the
database holds is a panel drawn over days nobody wrote, and a preset that
resolves to nothing -- `Custom`, or a window on an extent with no rows at all
-- falls back to the whole extent rather than to an empty bar.

The preset is written back to the session only once the bar is drawn, so a
rerun reopens the radio on the choice the operator just made. The fifth slot is
handed back as an empty placeholder rather than filled here: the line restating
what the filters narrowed to counts runs, which is not known until the first
wave of reads comes back, so the caller writes it into that slot then.

Streamlit is handed in rather than imported: it lives in the optional
``dashboard`` dependency group, and the window this bar resolves to is testable
without it.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from orchestrator.observability.dashboard import date_controls, windows


def initial_filter_window(
    preset_choice: str,
    extent: Any,
    extent_min_d: date,
    extent_max_d: date,
) -> windows.DateWindow:
    """The window the pickers open on: the preset's, or the whole extent."""
    return (
        windows.preset_window(preset_choice, extent)
        or windows.to_window(extent_min_d, extent_max_d)
    )


def render_date_inputs(
    st: Any,
    columns: date_controls.DateFilterColumns,
    initial_window: windows.DateWindow,
    extent_min_d: date,
    extent_max_d: date,
) -> tuple[date, date]:
    """Draw the two pickers on the inclusive days the window covers."""
    with columns.start:
        start_date = st.date_input(
            "From",
            value=initial_window.start.date(),
            min_value=extent_min_d,
            max_value=extent_max_d,
        )
    with columns.end:
        end_date = st.date_input(
            "To",
            value=(initial_window.end - timedelta(days=1)).date(),
            min_value=extent_min_d,
            max_value=extent_max_d,
        )
    return start_date, end_date


def render_date_filter_bar(
    *,
    st: Any,
    extent: Any,
    extent_min_d: date,
    extent_max_d: date,
) -> tuple[windows.DateWindow, Any]:
    """Render the preset and date-range controls."""
    if "preset" not in st.session_state:
        st.session_state.preset = windows.DEFAULT_PRESET
    with st.container(border=True):
        st.markdown(
            '<div class="orch-cardmark"></div>',
            unsafe_allow_html=True,
        )
        columns = date_controls.date_filter_columns(st)
        date_controls.render_date_filter_label(st, columns.label)
        preset_choice = date_controls.render_preset_choice(st, columns.preset)
        initial_window = initial_filter_window(
            preset_choice,
            extent,
            extent_min_d,
            extent_max_d,
        )
        dates = render_date_inputs(
            st,
            columns,
            initial_window,
            extent_min_d,
            extent_max_d,
        )
        with columns.meta:
            meta_slot = st.empty()
    st.session_state.preset = preset_choice
    return windows.to_window(*dates), meta_slot
