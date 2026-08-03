# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the adoption table's row projection.

The tone a quiet cell's counts and rate are drawn in, the two count and rate
readings behind them, the readings one cell is reduced to, and the row they are
rendered as are the dashboard owner's own objects. A caller that names this
module gets those rather than a copy, so a cohort with no session evidence and
one that was offered a skill and loaded it in none read the same way wherever
the table is drawn from.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import skill_adoption_rows


_muted_zero_html = skill_adoption_rows.muted_zero_html
_adoption_count_html = skill_adoption_rows.adoption_count_html
_adoption_rate_html = skill_adoption_rows.adoption_rate_html
SkillAdoptionRowView = skill_adoption_rows.SkillAdoptionRowView
_skill_adoption_row_view = skill_adoption_rows.skill_adoption_row_view
_skill_adoption_row_html = skill_adoption_rows.skill_adoption_row_html
