# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical skill-result import site, answered by the query owner.

The three cells are the owner's own classes, so the guarded share a caller
reads off one here is the share the skill readers publish.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.skill_models import (
    SkillAdoptionRow as SkillAdoptionRow,
    SkillTriggerMatrixRow as SkillTriggerMatrixRow,
    SkillTriggerRateRow as SkillTriggerRateRow,
)


_COMPATIBILITY_EXPORTS = (
    SkillAdoptionRow,
    SkillTriggerMatrixRow,
    SkillTriggerRateRow,
)
