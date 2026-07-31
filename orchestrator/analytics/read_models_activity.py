# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical time-bucketed result import site, answered by the query owner.

The three cells are the owner's own classes, so a row a caller unpacks here is
the row the activity readers built.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.activity_models import (
    BackendDailyTokensRow as BackendDailyTokensRow,
    HourlyHeatmapPoint as HourlyHeatmapPoint,
    ThroughputDayRow as ThroughputDayRow,
)


_COMPATIBILITY_EXPORTS = (
    BackendDailyTokensRow,
    HourlyHeatmapPoint,
    ThroughputDayRow,
)
