# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the chrome and the tiles beneath it.

The banner a page opens with, the line restating what its filters narrowed to,
the pill a tile's move is annotated with together with the tone and arrow it is
painted from, the strip the tiles are assembled into, the request the banner is
described by, and the two historical keyword surfaces in front of the pill and
the banner are the dashboard owner's own objects. A caller that names this
module -- or the HTML surface above it -- gets those rather than a copy, so the
strip a page renders and the markup the owner writes cannot come apart.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import summary_html


_TopbarRequest = summary_html.TopbarRequest
_plural_s = summary_html.plural_s
_delta_style = summary_html.delta_style
_delta_pill = summary_html.delta_pill
_topbar_html = summary_html.topbar_html
_filter_meta_html = summary_html.filter_meta_html
_kpi_strip_html = summary_html.kpi_strip_html
_DELTA_SIGNATURE = summary_html.DELTA_SIGNATURE
_TOPBAR_SIGNATURE = summary_html.TOPBAR_SIGNATURE
