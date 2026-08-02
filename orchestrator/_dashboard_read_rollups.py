# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the headline and lifecycle reads.

The seven a page's summary, activity, stage, run, spend, and review-round
sections are drawn from -- and the cap the run list is read under -- are the
dashboard owner's own objects. A caller that names this module -- the hub in
front of it, and every historical `dashboard.<name>` import through that hub --
reaches those rather than a copy of any of them, so a page and the owner cannot
answer differently.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import rollups


DEFAULT_RECENT_AGENT_EXITS = rollups.DEFAULT_RECENT_AGENT_EXITS
_read_summary = rollups.read_summary
_read_prev_kpi = rollups.read_prev_kpi
_read_time_series = rollups.read_time_series
_read_stage_breakdown = rollups.read_stage_breakdown
_read_recent_agent_exits = rollups.read_recent_agent_exits
_read_top_cost_issues = rollups.read_top_cost_issues
_read_review_round = rollups.read_review_round
