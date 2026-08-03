# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the two skill panels.

The adoption card, the caption that keeps it from nagging about a switch
already on, the invocation diagnostics folded beneath it, and the trigger-rate
card beside them with its own fold-out matrix are the dashboard owners' own
objects. A caller that names this module -- or the widget hub above it -- gets
those rather than a copy, so a panel the page draws and the one the owners
render cannot start reading the same window two ways.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import skill_panel, skill_trigger_panel


NO_AGENT_EXITS_MESSAGE = skill_trigger_panel.NO_AGENT_EXITS_MESSAGE
_render_skill_adoption = skill_panel.render_skill_adoption
_skill_adoption_zero_caption = skill_panel.skill_adoption_zero_caption
_skill_adoption_evidence_caption = skill_panel.skill_adoption_evidence_caption
_render_skill_invocation_diagnostics = (
    skill_panel.render_skill_invocation_diagnostics
)
_render_skill_triggers = skill_trigger_panel.render_skill_triggers
_render_skill_matrix_expander = skill_trigger_panel.render_skill_matrix_expander
