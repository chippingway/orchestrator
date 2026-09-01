# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Where a window's spend landed across the lifecycle, as two paired bars.

The two figures answer the same question along different axes -- which stage of
the issue lifecycle the money went to, and which review cycle it went to -- so
they are drawn beside each other rather than one under the other, and an
operator reads them as one comparison. The columns are split 7:5 rather than
evenly because the stage axis carries the wider vocabulary: a full stage name
needs the room that a round bucket, which is a digit or `6+`, does not.

Both figures are pinned to one height, computed off whichever of the two reads
came back with more rows. A horizontal bar family sizes itself by its own row
count, so two panels left to size themselves would stand at different heights
the moment one axis had more buckets than the other -- and a reader comparing
spend across the gutter would be comparing bars of two different thicknesses.

Streamlit is the caller's, handed in as a parameter, so this owner does not
name it. Both figures come off the chart owners directly, the way the header
above them comes off the markup owner: a panel is the card and the figure
inside it together, and a builder handed in would let the two be assembled from
different chart families -- which is how a pair pinned to one height ends up
drawn by two that measure it differently. Neither builder names Plotly at
module scope, reaching it inside its own call instead, so importing this owner
still works in the default install that does not carry it.

The Plotly configuration is read off the owner that holds it at call time
rather than bound here: it is the same decision for every figure on the page,
and it is handed over as a plain dict since that owner publishes a read-only
proxy Plotly cannot serialize.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from orchestrator.observability.analytics.query.cost_models import (
    ReviewRoundBucketRow,
)
from orchestrator.observability.analytics.query.run_models import StageBreakdown
from orchestrator.observability.dashboard import render_config
from orchestrator.observability.dashboard.card_html import card_header_html
from orchestrator.observability.dashboard.charts.cost_review import (
    cost_by_review_round,
)
from orchestrator.observability.dashboard.charts.cost_stage import cost_by_stage


TABLE_ROW_HEIGHT = 40
TABLE_BASE_HEIGHT = 80


def paired_bars_height(
    stage_rows: Sequence[StageBreakdown],
    review_rows: Sequence[ReviewRoundBucketRow],
) -> int:
    """The height both bar panels are pinned to, off the longer of the two."""
    row_count = max(len(stage_rows), len(review_rows), 1)
    return TABLE_ROW_HEIGHT * row_count + TABLE_BASE_HEIGHT


def render_stage_review_bars(
    *,
    st: Any,
    stage_rows: Sequence[StageBreakdown],
    review_round_rows: Sequence[ReviewRoundBucketRow],
) -> None:
    """Render aligned per-stage and per-review-round cost bars."""
    bars_height = paired_bars_height(stage_rows, review_round_rows)
    stage_column, round_column = st.columns([7, 5])
    with stage_column:
        with st.container(border=True):
            st.markdown(
                card_header_html(
                    "Cost by workflow stage",
                    "Where spend lands across the issue lifecycle",
                ),
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                cost_by_stage(stage_rows, height=bars_height),
                use_container_width=True,
                config=dict(render_config.PLOTLY_CONFIG),
            )
    with round_column:
        with st.container(border=True):
            st.markdown(
                card_header_html(
                    "Development and review by round",
                    "Developer and reviewer spend per review cycle",
                ),
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                cost_by_review_round(
                    review_round_rows,
                    height=bars_height,
                ),
                use_container_width=True,
                config=dict(render_config.PLOTLY_CONFIG),
            )
