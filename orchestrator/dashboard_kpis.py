# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the KPI arithmetic and the banners above it.

The delta math, the reliability triples, the top-cost ordering, and the rework
share are the KPI owner's own objects under `observability/dashboard/`, and the
two banner bands beside them the insight owner's. A caller that names this
module -- the KPI strip, the cost widgets, and every historical
`dashboard.<name>` import resolved through it -- reaches those rather than a
copy of any of them, so a page and the owners cannot answer differently.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import insights, kpis

DEFAULT_EXPENSIVE_LIMIT = kpis.DEFAULT_EXPENSIVE_LIMIT
REWORK_BUCKETS = kpis.REWORK_BUCKETS
kpi_delta = kpis.kpi_delta
reliability_tile_data = kpis.reliability_tile_data
top_expensive_issues = kpis.top_expensive_issues
rework_totals = kpis.rework_totals

FAILURE_RATE_BANNER_THRESHOLD = insights.FAILURE_RATE_BANNER_THRESHOLD
UNPRICED_COVERAGE_THRESHOLD = insights.UNPRICED_COVERAGE_THRESHOLD
UNPRICED_COST_SOURCES = insights.UNPRICED_COST_SOURCES
InsightBanner = insights.InsightBanner
compute_insights = insights.compute_insights
