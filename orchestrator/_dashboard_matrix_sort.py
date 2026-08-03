# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the skill matrix's ordering.

The parse a clicked header is read back through, the per-column ordering it
selects, and the repository-then-rate default a matrix nobody sorted opens in
are the dashboard owner's own objects. A caller that names this module gets
those rather than a copy, so the order a page draws and the one the owner
decides cannot disagree about which rows lead.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import skill_matrix_sort


parse_skill_matrix_sort = skill_matrix_sort.parse_skill_matrix_sort
_sort_skill_matrix_rows = skill_matrix_sort.sort_skill_matrix_rows
_default_sort_skill_matrix_rows = (
    skill_matrix_sort.default_sort_skill_matrix_rows
)
_skill_matrix_default_sort_key = (
    skill_matrix_sort.skill_matrix_default_sort_key
)
