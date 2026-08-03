# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the coverage bar, forwarding to its owner."""
from __future__ import annotations

from orchestrator.observability.dashboard import coverage_card


CoverageSegment = coverage_card.CoverageSegment
cost_coverage_weights = coverage_card.cost_coverage_weights
cost_source_color = coverage_card.cost_source_color
coverage_segment = coverage_card.coverage_segment
coverage_segments = coverage_card.coverage_segments
cost_coverage_bar_html = coverage_card.cost_coverage_bar_html
