# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the run's tallies, answered by their owner.

The seven functions are the owner's own, and they are the same objects the run
record binds its properties to, so a caller reading a cost off a run and one
calling the projection directly cannot get different answers.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import usage_views


tool_calls = usage_views.tool_calls
step_count = usage_views.step_count
model = usage_views.model
cost_usd = usage_views.cost_usd
cost_source = usage_views.cost_source
total_tokens = usage_views.total_tokens
usage_for_turn = usage_views.usage_for_turn
