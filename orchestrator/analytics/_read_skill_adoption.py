# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the adoption read, answered by its owner.

The three names are the owner's own, so the sessions a skill is measured
against, the window diagnostics that ride beside that ratio without moving it,
and the cap their ranking is trimmed to are all decided there.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.skill_adoption import (
    SKILL_ADOPTION_ROW_LIMIT as SKILL_ADOPTION_ROW_LIMIT,
    SkillAdoption as _SkillAdoption,
    skill_adoption_rows as _skill_adoption_rows,
)

_COMPATIBILITY_EXPORTS = (
    SKILL_ADOPTION_ROW_LIMIT,
    _SkillAdoption,
    _skill_adoption_rows,
)
