# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the hero spend and token-usage card.

The card the page opens with, the toggle deciding which stack it draws, and
the per-day totals that stack is built from are the dashboard owner's own
objects. A caller that names this module -- or the widget hub above it -- gets
those rather than a copy, so the card an operator reads and the one the owner
renders cannot start reporting a window two ways.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import usage_panel


_backend_tokens_by_day = usage_panel.backend_tokens_by_day
_stack_mode_label = usage_panel.stack_mode_label
_stack_mode_index = usage_panel.stack_mode_index
_render_hero_usage = usage_panel.render_hero_usage
