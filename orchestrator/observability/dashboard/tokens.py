# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The geometry and type the analytics page is laid out and set in.

The radii, card inset, grid gap, and content width the standalone mock's
`:root` block specifies, plus the IBM Plex Sans / Mono pair everything on the
page is typeset in. They sit apart from the colors because both surfaces that
consume them -- the Plotly layout defaults and the injected page CSS -- read
the measurements and the palette together, and a value changed here has to
move a chart and the card around it by the same amount.

Like the palette beside them these are plain data, so a caller reads a
measurement without the optional `dashboard` dependency group installed.
"""
from __future__ import annotations

RADIUS = "14px"
CARD_PADDING = "20px"
GRID_GAP = "16px"
CONTENT_MAX_WIDTH = "1480px"
# The sticky top bar's resting height -- the filter bar's `top:` sits
# one pixel below it so the two share a single border line when the
# operator scrolls.
TOPBAR_STICKY_HEIGHT = "71px"

FONT_FAMILY = (
    '"IBM Plex Sans", -apple-system, BlinkMacSystemFont, '
    '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
)
MONO_FONT_FAMILY = (
    '"IBM Plex Mono", ui-monospace, SFMono-Regular, "SF Mono", '
    'Menlo, Consolas, "Liberation Mono", monospace'
)
FONT_SIZE = 13
TITLE_FONT_SIZE = 15
