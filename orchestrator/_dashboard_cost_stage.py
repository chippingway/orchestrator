# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the per-stage cost split.

The seven columns a stage bar is drawn from, the full-price fallback and
ordering behind them, the shading a cache half is tinted with, and the builder
itself are the charts owner's own objects. The cost surface that names this
module reaches those rather than a copy, so a cache segment cannot be tinted
one way here and another under the owner.
"""
from __future__ import annotations

from orchestrator.observability.dashboard.charts import cost_stage


CACHE_LIGHTEN = cost_stage.CACHE_LIGHTEN
HEX_BASE = cost_stage.HEX_BASE
_StageCostBars = cost_stage.StageCostBars
_stage_no_cache_cost = cost_stage.stage_no_cache_cost
_reverse_stage_cost_bars = cost_stage.reverse_stage_cost_bars
_stage_cost_bars = cost_stage.stage_cost_bars
_stage_cost_sort_key = cost_stage.stage_cost_sort_key
cost_by_stage = cost_stage.cost_by_stage
_lighten_hex = cost_stage.lighten_hex
