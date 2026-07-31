# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the trigger matrix, answered by its owner.

The six names are the owner's own, so the repository-scoped catalog scan, the
window-scoped runs scan, the cells the first pads the second with, and the cap
their ranking is trimmed to are all decided there.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.skill_matrices import (
    SKILL_MATRIX_ROW_LIMIT as SKILL_MATRIX_ROW_LIMIT,
    SkillMatrixCounts as _SkillMatrixCounts,
    skill_catalog as _skill_catalog,
    skill_catalog_rows as _skill_catalog_rows,
    skill_run_rows as _skill_run_rows,
    skill_trigger_matrix_rows as _skill_trigger_matrix_rows,
)

_COMPATIBILITY_EXPORTS = (
    SKILL_MATRIX_ROW_LIMIT,
    _SkillMatrixCounts,
    _skill_catalog,
    _skill_catalog_rows,
    _skill_run_rows,
    _skill_trigger_matrix_rows,
)
