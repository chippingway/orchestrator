# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical window-result import site, answered by the query owner.

The four models are the owner's own classes, so an empty `Summary()` or
`FilterOptions()` built here is the one a page compares its read against.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.overview_models import (
    DataExtent as DataExtent,
    FilterOptions as FilterOptions,
    Summary as Summary,
    TimeSeriesPoint as TimeSeriesPoint,
)


_COMPATIBILITY_EXPORTS = (
    DataExtent,
    FilterOptions,
    Summary,
    TimeSeriesPoint,
)
