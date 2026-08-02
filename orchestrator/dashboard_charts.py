# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Plotly figure builders for the redesigned analytics dashboard.

Compatibility hub: the pure figure builders live in focused sibling modules,
and this module re-imports each public builder under its original name so
``dashboard_charts.<builder>`` keeps resolving for the widget pipeline and the
existing tests. Every builder takes already-fetched read-model rows (or a raw
matrix for the 7x24 heatmap) and returns a ``plotly.graph_objects.Figure``;
the dashboard layer owns the query + sidebar filters and hands the resulting
``Figure`` to ``st.plotly_chart``.

The chart families and their homes. A family still holding its own builders
imports the shared low-level primitives it needs one-directionally through
``orchestrator.dashboard_charts_base``, the historical site in front of the
owner holding them, so a direct import of any of them is cycle-free; a family
that has moved names that owner directly:

- ``orchestrator.dashboard_charts_usage`` -- ``usage_over_time`` (stacked-area
  daily token consumption with a cost-line overlay, in token-type or
  per-backend stack mode) and the ``backend_per_day`` stub that feeds its
  per-backend stack.
- ``orchestrator.dashboard_charts_cost`` -- the horizontal cost-bar family
  (``cost_horizontal_bars`` / ``cost_by_repo`` / ``cost_by_stage`` /
  ``cost_by_review_round``).
- ``orchestrator.dashboard_charts_heatmap`` -- ``hour_weekday_heatmap``, the
  7x24 weekday-by-hour token-volume heatmap, forwarded from the charts owner
  that builds it.
- ``orchestrator.dashboard_charts_throughput`` -- ``done_per_day_bars``, the
  issues-resolved-per-day reliability strip, forwarded from the charts owner
  that builds it.

Plotly is imported at module load in the family modules that still hold their
own builders, because they are only reachable from the lazy ``import`` inside
``orchestrator.dashboard.main`` (see the lazy-import guard in
``tests/test_dashboard.py``): the orchestrator polling tick must not import
this module, and ``orchestrator/dashboard.py`` must not import it at module
load -- both invariants are enforced by tests. A family that has moved under
``observability`` reaches Plotly inside the call that builds its figure
instead, so importing the owner costs nothing in the default install.
"""
from __future__ import annotations

from orchestrator.dashboard_charts_cost import (
    cost_by_repo as cost_by_repo,
    cost_by_review_round as cost_by_review_round,
    cost_by_stage as cost_by_stage,
    cost_horizontal_bars as cost_horizontal_bars,
)
from orchestrator.dashboard_charts_heatmap import (
    hour_weekday_heatmap as hour_weekday_heatmap,
)
from orchestrator.dashboard_charts_throughput import (
    done_per_day_bars as done_per_day_bars,
)
from orchestrator.dashboard_charts_usage import (
    backend_per_day as backend_per_day,
    usage_over_time as usage_over_time,
)


# The hub exposes these names by attribute; retaining an explicit inventory
# keeps that compatibility surface visible to static import analysis.
_COMPATIBILITY_EXPORTS = (
    backend_per_day,
    cost_by_repo,
    cost_by_review_round,
    cost_by_stage,
    cost_horizontal_bars,
    done_per_day_bars,
    hour_weekday_heatmap,
    usage_over_time,
)
