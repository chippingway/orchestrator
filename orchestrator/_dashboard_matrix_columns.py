# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the skill matrix's column vocabulary.

The seven columns the invocation-level trigger matrix is read across, the key
each is ordered by, the subset a first click sorts descending, and the pair of
query parameters its headers write are the dashboard owner's own objects. A
caller that names this module gets those rather than a copy, so the header a
page links from and the parse that reads it back cannot start spelling one sort
two ways.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import skill_matrix_columns


SkillMatrixColumn = skill_matrix_columns.SkillMatrixColumn
SKILL_MATRIX_COLUMNS = skill_matrix_columns.SKILL_MATRIX_COLUMNS
SKILL_MATRIX_NUMERIC_KEYS = skill_matrix_columns.SKILL_MATRIX_NUMERIC_KEYS
SKILL_MATRIX_SORT_KEYS = skill_matrix_columns.SKILL_MATRIX_SORT_KEYS
SKILL_MATRIX_SORT_PARAM = skill_matrix_columns.SKILL_MATRIX_SORT_PARAM
SKILL_MATRIX_DIR_PARAM = skill_matrix_columns.SKILL_MATRIX_DIR_PARAM
