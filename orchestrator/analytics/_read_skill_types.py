# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the skill keys, answered by the two owners.

The six names split by what asks for them: the cohort key and the two cells
built from it belong to the owner that normalizes a cohort, and the identity
column offsets to the owner that reads a session key off either scan.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.skill_sessions import (
    SESSION_ID_INDEX as _SESSION_ID_INDEX,
    SESSION_RESUME_INDEX as _SESSION_RESUME_INDEX,
    SESSION_ROW_INDEX as _SESSION_ROW_INDEX,
)
from orchestrator.observability.analytics.query.skill_values import (
    SkillAdoptionKey as _SkillAdoptionKey,
    SkillCohort as _SkillCohort,
    SkillMatrixKey as _SkillMatrixKey,
)

_COMPATIBILITY_EXPORTS = (
    _SESSION_ID_INDEX,
    _SESSION_RESUME_INDEX,
    _SESSION_ROW_INDEX,
    _SkillAdoptionKey,
    _SkillCohort,
    _SkillMatrixKey,
)
