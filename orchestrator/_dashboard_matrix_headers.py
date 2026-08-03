# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the skill matrix's sortable header row.

What a click on one heading offers, the link and arrow it is drawn as, and the
header row they are assembled into are the dashboard owner's own objects. A
caller that names this module gets those rather than a copy, so the parameters
a header writes stay the ones the matrix's parse reads back.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import skill_matrix_headers


SkillMatrixHeaderState = skill_matrix_headers.SkillMatrixHeaderState
_skill_matrix_header_state = skill_matrix_headers.skill_matrix_header_state
_skill_matrix_header_cell = skill_matrix_headers.skill_matrix_header_cell
_skill_matrix_header_html = skill_matrix_headers.skill_matrix_header_html
