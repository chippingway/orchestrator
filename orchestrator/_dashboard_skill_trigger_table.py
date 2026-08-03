# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the aggregate skill-trigger table.

The six columns each cohort's skill use is reported in, the rules its rate bar
is painted by, the label a cohort with no role or backend is read under, the
row one cohort is rendered as, and the panel they are assembled into are the
dashboard owner's own objects. A caller that names this module -- or the HTML
surface above it -- gets those rather than a copy, so the rates a page draws
and the ones the owner builds cannot start disagreeing about what a cohort
triggered.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import skill_trigger_table


UNKNOWN = skill_trigger_table.UNKNOWN
SKILL_TRIGGERS_TABLE_COLUMNS = skill_trigger_table.SKILL_TRIGGERS_TABLE_COLUMNS
SKILL_TRIGGERS_EXTRA_CSS = skill_trigger_table.SKILL_TRIGGERS_EXTRA_CSS
_skill_trigger_row_html = skill_trigger_table.skill_trigger_row_html
_skill_triggers_html = skill_trigger_table.skill_triggers_html
