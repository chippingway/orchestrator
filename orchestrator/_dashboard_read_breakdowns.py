# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the panel reads, and home of the skill one.

The six comparison reads are the dashboard owner's own objects. A caller that
names this module -- the read plan beside it, the hub in front of them, and
every historical `dashboard.<name>` import through that hub -- reaches those
rather than a copy of any of them, so a page and the owner cannot answer
differently.

`_read_skill_trigger_rates` is spelled here rather than forwarded, because the
skill reads belong together: it is the third of the trio `_dashboard_read_skills`
holds the other two of, and it waits here for the owner that will take all
three.
"""
from __future__ import annotations

from orchestrator._dashboard_read_core import _read_filtered
from orchestrator.observability.analytics.query import skill_reads
from orchestrator.observability.dashboard import breakdowns


_read_backend_efficiency = breakdowns.read_backend_efficiency
_read_repo_breakdown = breakdowns.read_repo_breakdown
_read_cost_coverage = breakdowns.read_cost_coverage
_read_hourly_heatmap = breakdowns.read_hourly_heatmap
_read_throughput = breakdowns.read_throughput
_read_backend_daily_tokens = breakdowns.read_backend_daily_tokens


def _read_skill_trigger_rates(key: tuple):
    # Named on the query owner beside its two siblings under
    # `_dashboard_read_skills`, so no skill read reaches the compatibility
    # facade the reads around it still resolve through.
    return _read_filtered(skill_reads.get_skill_trigger_rates, key)
