# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one theme object a page hands every panel it draws.

The panel owners take the theme as a parameter rather than importing one, so
that a section can be rendered against a marking stand-in and so that no owner
under this package binds a page's chrome at import. Something still has to
compose the object they are handed, and this is it: the five style owners --
the palette, the geometry and type tokens, the Plotly layout assembled from
both, the page stylesheet, and the compact formatters -- read back through one
name, so `theme.ACCENT` and the palette's own `ACCENT` are the same value and a
card tinted through either lands on the same hue.

Every name here is the owner's own object, re-exported rather than rebuilt.
This module implements nothing and imports neither Plotly nor Streamlit, so a
caller may name it at module load in an install carrying none of the optional
`dashboard` group.
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
