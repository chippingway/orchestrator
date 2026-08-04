# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the visual theme the dashboards share.

`from orchestrator import dashboard_theme as theme` is how the analytics page
and the trajectory viewer's historical surface beside it reach one palette, one
set of geometry and type tokens, the Plotly layout assembled from both, the
page stylesheet, and the compact number formatters -- the chart families name
those owners themselves. Every one of these names is the owner's own object,
re-exported here rather than rebuilt, so `theme.ACCENT` and the owner's
`ACCENT` are the same value and a chart drawn through either lands on the same
grid.

This module implements nothing and imports neither Plotly nor Streamlit. The
analytics page reaches it inside `load_dashboard_modules`, beside pandas and
the chart hub, so an ordinary import of either of that page's launch paths
carries none of it. Staying free of both is what keeps the site reachable from
anywhere else: it is a compatibility surface, so a caller may name it at module
load in an install carrying no optional `dashboard` group at all.
"""
from __future__ import annotations

from orchestrator.observability.dashboard.css import PAGE_CSS as PAGE_CSS
from orchestrator.observability.dashboard.formatting import (
    fmt_money as fmt_money,
    fmt_money_exact as fmt_money_exact,
    fmt_num as fmt_num,
    fmt_tokens as fmt_tokens,
)
from orchestrator.observability.dashboard.layout import base_layout as base_layout
from orchestrator.observability.dashboard.palette import (
    BACKGROUND as BACKGROUND,
    BORDER as BORDER,
    CARD_BG as CARD_BG,
    GRID as GRID,
    MUTED_TEXT as MUTED_TEXT,
    MUTED_TEXT_SOFT as MUTED_TEXT_SOFT,
    SURFACE as SURFACE,
    TEXT as TEXT,
)
from orchestrator.observability.dashboard.palette import (
    ACCENT as ACCENT,
    DANGER as DANGER,
    INK as INK,
    NEUTRAL as NEUTRAL,
    PRIMARY as PRIMARY,
    SECONDARY as SECONDARY,
    SUCCESS as SUCCESS,
    WARNING as WARNING,
)
from orchestrator.observability.dashboard.palette import (
    AGENT_ROLE_COLORS as AGENT_ROLE_COLORS,
    BACKEND_COLORS as BACKEND_COLORS,
    CATEGORICAL_PALETTE as CATEGORICAL_PALETTE,
    COST_SOURCE_COLORS as COST_SOURCE_COLORS,
    EVENT_COLORS as EVENT_COLORS,
    REVIEW_ROUND_COLORS as REVIEW_ROUND_COLORS,
    STAGE_COLORS as STAGE_COLORS,
    TOKEN_TYPE_COLORS as TOKEN_TYPE_COLORS,
)
from orchestrator.observability.dashboard.palette import color_for as color_for
from orchestrator.observability.dashboard.tokens import (
    CARD_PADDING as CARD_PADDING,
    CONTENT_MAX_WIDTH as CONTENT_MAX_WIDTH,
    GRID_GAP as GRID_GAP,
    RADIUS as RADIUS,
    TOPBAR_STICKY_HEIGHT as TOPBAR_STICKY_HEIGHT,
)
from orchestrator.observability.dashboard.tokens import (
    FONT_FAMILY as FONT_FAMILY,
    FONT_SIZE as FONT_SIZE,
    MONO_FONT_FAMILY as MONO_FONT_FAMILY,
    TITLE_FONT_SIZE as TITLE_FONT_SIZE,
)
