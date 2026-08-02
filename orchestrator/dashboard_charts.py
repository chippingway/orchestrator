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

The chart families and their homes. Every builder is defined by an owner under
``observability``, which names the primitives and theme owners it draws with
directly; each family surface below forwards that owner's object rather than
holding one of its own:

- ``orchestrator.dashboard_charts_usage`` -- ``usage_over_time`` (stacked-area
  daily token consumption with a cost-line overlay, in token-type or
  per-backend stack mode) and the ``backend_per_day`` stub beside it.
- ``orchestrator.dashboard_charts_cost`` -- the horizontal cost-bar family:
  ``cost_horizontal_bars``, the generic ranking; ``cost_by_repo``, the
  per-repository adapter drawn through it; ``cost_by_stage``, the per-stage
  cache split; and ``cost_by_review_round``, the same split across the two
  roles of a review round.
- ``orchestrator.dashboard_charts_heatmap`` -- ``hour_weekday_heatmap``, the
  7x24 weekday-by-hour token-volume heatmap.
- ``orchestrator.dashboard_charts_throughput`` -- ``done_per_day_bars``, the
  issues-resolved-per-day reliability strip.

No module on any of those paths imports Plotly at module load: an owner
reaches it inside the call that builds its figure, so importing one costs
nothing in the default install. The lazy ``import`` inside
``orchestrator.dashboard.main`` is still the only route to this hub (see the
lazy-import guard in ``tests/test_dashboard.py``): the orchestrator polling
tick must not import this module, and ``orchestrator/dashboard.py`` must not
import it at module load -- both invariants are enforced by tests.
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
