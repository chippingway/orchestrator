# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The Plotly layout every chart on the analytics page is drawn with.

What comes back is a plain dict, which is what lets this owner assemble
everything the chart builders share -- margins, font, gridlines, legend, and
backgrounds -- without importing Plotly, a package the optional `dashboard`
dependency group carries. A builder merges it through
`fig.update_layout(**base_layout(title=...))`, so a chart added later lands on
the same grid and type as the ones beside it rather than restating them.

The plot background is the card color rather than the page color: every chart
renders inside a card, so a figure painted the page's gray would read as a hole
punched in the card around it.
"""
from __future__ import annotations

from typing import Any, Optional

from orchestrator.observability.dashboard.palette import (
    CARD_BG,
    GRID,
    MUTED_TEXT,
    TEXT,
)
from orchestrator.observability.dashboard.tokens import (
    FONT_FAMILY,
    FONT_SIZE,
    TITLE_FONT_SIZE,
)

# Plotly layout dict key repeated across axis/legend/font configs.
_COLOR_KEY = "color"
# Chart top-margin (px): taller when a title is drawn, compact when not.
_MARGIN_TOP = 32
_MARGIN_TOP_COMPACT = 16


def base_layout(title: Optional[str] = None) -> dict[str, Any]:
    """Return the shared Plotly `layout` dict for a chart."""
    layout: dict[str, Any] = {
        "paper_bgcolor": CARD_BG,
        "plot_bgcolor": CARD_BG,
        "font": {
            "family": FONT_FAMILY,
            "size": FONT_SIZE,
            _COLOR_KEY: TEXT,
        },
        "margin": {"l": 56, "r": 24, "t": _MARGIN_TOP if title else _MARGIN_TOP_COMPACT, "b": 40},
        "legend": {
            "bgcolor": CARD_BG,
            "bordercolor": GRID,
            "borderwidth": 0,
        },
        "xaxis": {
            "gridcolor": GRID,
            "linecolor": GRID,
            "zerolinecolor": GRID,
            "tickfont": {_COLOR_KEY: MUTED_TEXT},
        },
        "yaxis": {
            "gridcolor": GRID,
            "linecolor": GRID,
            "zerolinecolor": GRID,
            "tickfont": {_COLOR_KEY: MUTED_TEXT},
        },
    }
    if title:
        layout["title"] = {
            "text": title,
            "font": {
                "family": FONT_FAMILY,
                "size": TITLE_FONT_SIZE,
                _COLOR_KEY: TEXT,
            },
        }
    return layout
