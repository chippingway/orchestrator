# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable skill-adoption surface backed by the dashboard owners.

`from orchestrator.dashboard_skill_adoption import _skill_adoption_html` is how
the widget sections and every historical `dashboard.<name>` import reach the
per-session adoption table, and `parse_skill_adoption_sort` how a page reads a
clicked header back out of its URL. The columns, the ordering, the header row,
the row projection, and the panel they are assembled into are the owners' own
objects under `observability/dashboard/`, published here under the spellings a
caller always imported them by, so a page and the owners cannot draw one table
two ways.
"""
from __future__ import annotations

from orchestrator import _dashboard_adoption_columns as columns
from orchestrator import _dashboard_adoption_headers as headers
from orchestrator import _dashboard_adoption_render as rendering
from orchestrator import _dashboard_adoption_rows as rows
from orchestrator import _dashboard_adoption_sort as sorting


SKILL_ADOPTION_EMPTY_MESSAGE = rendering.SKILL_ADOPTION_EMPTY_MESSAGE
_SKILL_ADOPTION_EXTRA_CSS = rendering.SKILL_ADOPTION_EXTRA_CSS
_SkillAdoptionColumn = columns.SkillAdoptionColumn
_SKILL_ADOPTION_COLUMNS = columns.SKILL_ADOPTION_COLUMNS
_SKILL_ADOPTION_NUMERIC_KEYS = columns.SKILL_ADOPTION_NUMERIC_KEYS
_SKILL_ADOPTION_SORT_KEYS = columns.SKILL_ADOPTION_SORT_KEYS
SKILL_ADOPTION_SORT_PARAM = columns.SKILL_ADOPTION_SORT_PARAM
SKILL_ADOPTION_DIR_PARAM = columns.SKILL_ADOPTION_DIR_PARAM
parse_skill_adoption_sort = sorting.parse_skill_adoption_sort
_sort_skill_adoption_rows = sorting._sort_skill_adoption_rows
_default_sort_skill_adoption_rows = sorting._default_sort_skill_adoption_rows
_skill_adoption_default_sort_key = sorting._skill_adoption_default_sort_key
_SkillAdoptionHeaderState = headers.SkillAdoptionHeaderState
_skill_adoption_header_state = headers._skill_adoption_header_state
_skill_adoption_header_cell = headers._skill_adoption_header_cell
_skill_adoption_header_html = headers._skill_adoption_header_html
_muted_zero_html = rows._muted_zero_html
_adoption_count_html = rows._adoption_count_html
_adoption_rate_html = rows._adoption_rate_html
_SkillAdoptionRowView = rows.SkillAdoptionRowView
_skill_adoption_row_view = rows._skill_adoption_row_view
_skill_adoption_row_html = rows._skill_adoption_row_html
_skill_adoption_html = rendering._skill_adoption_html
