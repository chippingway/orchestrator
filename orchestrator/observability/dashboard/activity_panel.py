# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""When the window's agents actually ran, as a weekday-by-hour grid.

Every panel above this one reduces a window to a reading -- a total, a
ranking, a rate -- and each of those is blind to the clock. This one keeps it:
the same tokens laid out by the hour and the weekday they landed on, so a
window that reads as steady spend can still show itself as two overnight
bursts.

An hour only means something in a zone, so the one control the page has over
that zone sits inside this card rather than in the sidebar beside the filters.
It is the only selection on the page that changes what a figure means rather
than which rows reach it, and the help text says so: the offset moves the
grid's buckets and the run listing's `ts` column together, over instants the
database keeps in UTC.

Nothing here shifts a timestamp. The cells arrive already bucketed, because
the read behind them was issued under the offset the page picked up from the
same session key this selectbox writes -- so the zone named in the header and
on the x-axis is true only as long as the two stay one key. What this owner
decides is that label and the card around it.

Streamlit is the caller's, handed in as a parameter, so this owner does not
name it. The figure comes off the chart owner directly, the way the header
comes off the markup owner: a panel is the card and the figure inside it
together, and a builder handed in would let this grid be assembled from a
chart family the panels above it were not. That builder reaches Plotly inside
its own call, so importing this owner still works in the default install that
does not carry it.

The Plotly configuration is read off the owner that holds it at call time
rather than bound here: it is the same decision for every figure on the page,
and it is handed over as a plain dict since that owner publishes a read-only
proxy Plotly cannot serialize.
"""
from __future__ import annotations

from typing import Any, Sequence

from orchestrator.observability.analytics.query.activity_models import (
    HourlyHeatmapPoint,
)
from orchestrator.observability.dashboard import render_config
from orchestrator.observability.dashboard.card_html import card_header_html
from orchestrator.observability.dashboard.charts.heatmap import (
    hour_weekday_heatmap,
)
from orchestrator.observability.dashboard.filters import (
    TZ_OFFSET_OPTIONS,
    format_tz_offset,
)


CARD_TITLE = "When agents run"

TZ_SELECT_LABEL = "Timezone"

# The key the picked offset is remembered under. The page reads it back at the
# top of the next rerun to issue the heatmap read, so the widget and that read
# have to name the same one.
TZ_OFFSET_STATE_KEY = "tz_offset_hours"

TZ_SELECT_HELP = (
    'Shifts heatmap bucketing and the "Recent agent runs" '
    "`ts` column to the selected UTC offset. `ts` is stored in UTC."
)


def card_subtitle(timezone_label: str) -> str:
    """Name the zone the grid's hour columns are already bucketed in."""
    return f"Token volume by hour ({timezone_label}) × weekday"


def render_activity_heatmap(
    *,
    st: Any,
    heatmap_rows: Sequence[HourlyHeatmapPoint],
    tz_offset_choice: int,
) -> None:
    """Render the weekday-by-hour token-volume heatmap."""
    timezone_label = format_tz_offset(int(tz_offset_choice))
    with st.container(border=True):
        st.markdown(
            card_header_html(CARD_TITLE, card_subtitle(timezone_label)),
            unsafe_allow_html=True,
        )
        st.selectbox(
            TZ_SELECT_LABEL,
            TZ_OFFSET_OPTIONS,
            key=TZ_OFFSET_STATE_KEY,
            format_func=format_tz_offset,
            help=TZ_SELECT_HELP,
        )
        st.plotly_chart(
            hour_weekday_heatmap(heatmap_rows, tz_label=timezone_label),
            use_container_width=True,
            config=dict(render_config.PLOTLY_CONFIG),
        )
