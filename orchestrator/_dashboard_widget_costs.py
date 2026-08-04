# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The activity card, and the three sections a window is compared in above it.

The paired lifecycle bars, the ranking of a window's costliest issues beside
the backends that ran them, and the repository spend beside the run-health
tiles are the dashboard owners' own renders. A caller that names this module --
or the widget hub above it -- gets those rather than a copy, so the section an
operator reads and the one a fix under the owners reaches cannot report the
same window two ways. The height both bars are pinned to and the notice a
window with no `agent_exit` row is answered with come from the same owners,
under the spellings the page always imported them by.
"""
from __future__ import annotations

from typing import Any

from orchestrator.dashboard_cards import _card_header_html
from orchestrator.observability.dashboard import (
    issue_cost_panel,
    reliability_panel,
    stage_cost_panel,
)
from orchestrator.dashboard_state import (
    TZ_OFFSET_OPTIONS,
    format_tz_offset,
)


_TABLE_ROW_HEIGHT = stage_cost_panel.TABLE_ROW_HEIGHT
_TABLE_BASE_HEIGHT = stage_cost_panel.TABLE_BASE_HEIGHT
NO_AGENT_EXITS_MESSAGE = issue_cost_panel.NO_AGENT_EXITS_MESSAGE
_render_stage_review_bars = stage_cost_panel.render_stage_review_bars
_paired_bars_height = stage_cost_panel.paired_bars_height
_render_issues_and_backends = issue_cost_panel.render_issues_and_backends
_render_repo_and_reliability = reliability_panel.render_repo_and_reliability


def _render_activity_heatmap(
    *,
    st: Any,
    dashboard_charts: Any,
    heatmap_rows: Any,
    tz_offset_choice: int,
) -> None:
    """Render the weekday-by-hour token-volume heatmap."""
    from orchestrator import dashboard as _dashboard

    timezone_label = format_tz_offset(int(tz_offset_choice))
    with st.container(border=True):
        st.markdown(
            _card_header_html(
                "When agents run",
                f"Token volume by hour ({timezone_label}) × weekday",
            ),
            unsafe_allow_html=True,
        )
        st.selectbox(
            "Timezone",
            TZ_OFFSET_OPTIONS,
            key="tz_offset_hours",
            format_func=format_tz_offset,
            help=(
                'Shifts heatmap bucketing and the "Recent agent runs" '
                "`ts` column to the selected UTC offset. `ts` is stored in UTC."
            ),
        )
        st.plotly_chart(
            dashboard_charts.hour_weekday_heatmap(
                heatmap_rows,
                tz_label=timezone_label,
            ),
            use_container_width=True,
            config=dict(_dashboard.PLOTLY_CONFIG),
        )
