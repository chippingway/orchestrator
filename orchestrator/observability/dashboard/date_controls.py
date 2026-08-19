# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The row a date filter is laid out in, and the controls framing its pickers.

One owner for the five slots the bar is drawn across and the two widgets that
sit beside its date pickers, because the layout and the preset radio are one
decision: the label names the bar in the first slot, the preset is clicked in
the second, the window it stands for is picked in the third and fourth, and the
fifth is the room the caller writes its filter line into. A slot added here
with no widget to fill it is a gap in the bar, and a widget drawn without a
slot to hold it lands wherever the page last left off.

The presets offered inline are named once, because the options the radio lists
and the position the current one is preselected at are read off the same
tuple. A preset offered by one and unknown to the other would fall to the last
option, which is how a bar could reopen on `All` after every rerun.

Streamlit is handed in rather than imported: it lives in the optional
``dashboard`` dependency group, and the layout these functions decide is
testable without it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orchestrator.observability.dashboard import windows


# The presets the bar exposes inline, widest last, since an unoffered one opens
# the radio on the final button. `Custom` is deliberately not among them: it
# names no window of its own, so it stays the sidebar fallback rather than one
# more button that resolves to nothing.
INLINE_PRESETS = (
    windows.PRESET_RECENT_THREE_DAYS,
    windows.PRESET_RECENT_WEEK,
    windows.PRESET_RECENT_THIRTY_DAYS,
    windows.PRESET_ALL,
)


@dataclass(frozen=True)
class DateFilterColumns:
    """The five slots one filter bar is drawn across, in page order."""

    label: Any
    preset: Any
    start: Any
    end: Any
    meta: Any


def date_filter_columns(st: Any) -> DateFilterColumns:
    """Lay the bar out as five bottom-aligned slots."""
    columns = st.columns(
        [1.0, 1.7, 1.4, 1.4, 3.0],
        vertical_alignment="bottom",
    )
    return DateFilterColumns(*columns)


def render_date_filter_label(st: Any, column: Any) -> None:
    """Name the bar, and mark where the sticky chrome anchors to it."""
    with column:
        st.markdown(
            '<div class="orch-filterbar-anchor"></div>'
            '<span class="orch-filter-label">Date range</span>',
            unsafe_allow_html=True,
        )


def preset_radio_index(preset: str) -> int:
    """Where the radio opens for a preset, falling back to the widest one."""
    if preset not in INLINE_PRESETS:
        return len(INLINE_PRESETS) - 1
    return INLINE_PRESETS.index(preset)


def render_preset_choice(st: Any, column: Any) -> str:
    """Offer the inline presets, opened on the session's own choice."""
    with column:
        return st.radio(
            "Range preset",
            options=INLINE_PRESETS,
            format_func=lambda preset: windows.PRESET_INLINE_LABELS[preset],
            index=preset_radio_index(st.session_state.preset),
            horizontal=True,
            label_visibility="collapsed",
            key="_preset_radio",
        )
