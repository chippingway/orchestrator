# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The repository-spend and activity cards, and the two comparisons above them.

The paired lifecycle bars and the ranking of a window's costliest issues beside
the backends that ran them are the dashboard owners' own renders. A caller that
names this module -- or the widget hub above it -- gets those rather than a
copy, so the section an operator reads and the one a fix under the owners
reaches cannot report the same window two ways. The height both bars are pinned
to and the notice a window with no `agent_exit` row is answered with come from
the same owners, under the spellings the page always imported them by.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from orchestrator import _dashboard_widget_models as models
from orchestrator.dashboard_cards import (
    _card_header_html,
    _reliability_tiles_html,
)
from orchestrator.observability.dashboard import issue_cost_panel, stage_cost_panel
from orchestrator.observability.dashboard.kpis import reliability_tile_data
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


def _render_repo_and_reliability(
    modules: models._DashboardModules,
    panel: models._ReliabilityPanelData,
) -> None:
    """Render repository spend and reliability throughput."""
    from orchestrator import dashboard as _dashboard

    repo_column, reliability_column = modules.st.columns([7, 5])
    with repo_column:
        with modules.st.container(border=True):
            modules.st.markdown(
                _card_header_html("Cost by repository", "Spend across managed repos"),
                unsafe_allow_html=True,
            )
            modules.st.plotly_chart(
                modules.charts.cost_by_repo(panel.repos),
                use_container_width=True,
                config=dict(_dashboard.PLOTLY_CONFIG),
            )
    with reliability_column:
        with modules.st.container(border=True):
            modules.st.markdown(
                _card_header_html(
                    "Reliability & throughput",
                    "Run health and issues resolved per day",
                ),
                unsafe_allow_html=True,
            )
            raw_tiles = reliability_tile_data(
                panel.summary,
                resolved=panel.resolved,
                rejected=panel.rejected,
            )
            modules.st.markdown(
                _reliability_tiles_html(
                    raw_tiles,
                    fmt_num=modules.theme.fmt_num,
                ),
                unsafe_allow_html=True,
            )
            modules.st.plotly_chart(
                modules.charts.done_per_day_bars(
                    panel.throughput,
                    window_start=panel.window.start.date(),
                    window_end=(panel.window.end - timedelta(days=1)).date(),
                    title=None,
                ),
                use_container_width=True,
                config=dict(_dashboard.PLOTLY_CONFIG),
            )


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
