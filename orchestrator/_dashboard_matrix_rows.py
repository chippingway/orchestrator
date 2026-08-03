# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the skill matrix's row projection.

The tone a quiet cell's count and rate are drawn in, the readings one cell is
reduced to, and the row they are rendered as are the dashboard owner's own
objects. A caller that names this module gets those rather than a copy, so an
offered-but-never-triggered cell reads the same way wherever the matrix is
drawn from.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import skill_matrix_rows


_muted_zero_html = skill_matrix_rows.muted_zero_html
SkillMatrixRowView = skill_matrix_rows.SkillMatrixRowView
_skill_matrix_row_view = skill_matrix_rows.skill_matrix_row_view
_skill_matrix_row_html = skill_matrix_rows.skill_matrix_row_html
