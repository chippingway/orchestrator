# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable dashboard card surface backed by focused card leaves.

`from orchestrator.dashboard_cards import _card_header_html` is how the widget
sections and every historical `dashboard.<name>` import reach the header a
panel is titled by, the banner stack a page opens with, the reliability strip
beneath its headline tiles, the per-backend efficiency card, and the
cost-attribution coverage bar. Each of those is the owner's own object under
`observability/dashboard/`, published here under the private spellings a caller
always imported it by, so a page and the owners cannot draw a card differently.
"""
from __future__ import annotations

from orchestrator import _dashboard_backend_card as backend
from orchestrator import _dashboard_card_headers as headers
from orchestrator import _dashboard_coverage_card as coverage


_card_header_html = headers.card_header_html
_insights_html = headers.insights_html
_backend_efficiency_card_html = backend.backend_efficiency_card_html
_BackendEfficiencyMetrics = backend.BackendEfficiencyMetrics
_safe_ratio = backend.safe_ratio
_backend_efficiency_metrics = backend.backend_efficiency_metrics
_cost_coverage_weights = coverage.cost_coverage_weights
_cost_source_color = coverage.cost_source_color
_CoverageSegment = coverage.CoverageSegment
_coverage_segment = coverage.coverage_segment
_coverage_segments = coverage.coverage_segments
_cost_coverage_bar_html = coverage.cost_coverage_bar_html
_reliability_tiles_html = headers.reliability_tiles_html
