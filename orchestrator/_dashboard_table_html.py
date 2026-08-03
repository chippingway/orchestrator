# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the shared compact-table markup.

The stylesheet a panel scopes to itself, the header and body it is assembled
from, and the four readings a cell is built out of are the dashboard owner's
own objects. A caller that names this module -- the HTML surface in front of
it, and the two table leaves that reach it directly -- gets those rather than a
copy of any of them, so every panel on the page keeps being drawn by one table.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import tables


_table_css = tables.table_css
_table_head_html = tables.table_head_html
_table_html = tables.table_html
_relative_width_pct = tables.relative_width_pct
_short_repo_name = tables.short_repo_name
_int_or_zero = tables.int_or_zero
_money_or_dash = tables.money_or_dash
