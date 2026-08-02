# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the panel reads.

The six comparison reads and the skill-trigger rates beside them are the
dashboard owners' own objects. A caller that names this module -- the hub in
front of it, and every historical `dashboard.<name>` import through that hub --
reaches those rather than a copy of any of them, so a page and the owner cannot
answer differently.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import breakdowns, skills


_read_backend_efficiency = breakdowns.read_backend_efficiency
_read_repo_breakdown = breakdowns.read_repo_breakdown
_read_cost_coverage = breakdowns.read_cost_coverage
_read_hourly_heatmap = breakdowns.read_hourly_heatmap
_read_throughput = breakdowns.read_throughput
_read_backend_daily_tokens = breakdowns.read_backend_daily_tokens
_read_skill_trigger_rates = skills.read_skill_trigger_rates
