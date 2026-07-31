# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical coverage / token / heatmap import site, answered by the owners.

The six names are the three owners' own functions, so the cost source a
coverage bar keeps verbatim, the full-window scan a backend stack is summed
over, and the bound offset a heatmap buckets in are each decided once whichever
module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.backend_tokens import (
    backend_daily_token_rows as _backend_daily_token_rows,
    backend_daily_tokens_from_row as _backend_daily_tokens_from_row,
)
from orchestrator.observability.analytics.query.cost_coverage import (
    cost_coverage_from_row as _cost_coverage_from_row,
    cost_coverage_rows as _cost_coverage_rows,
)
from orchestrator.observability.analytics.query.hourly_heatmaps import (
    hourly_heatmap_from_row as _hourly_heatmap_from_row,
    hourly_heatmap_rows as _hourly_heatmap_rows,
)


_COMPATIBILITY_EXPORTS = (
    _backend_daily_token_rows,
    _backend_daily_tokens_from_row,
    _cost_coverage_from_row,
    _cost_coverage_rows,
    _hourly_heatmap_from_row,
    _hourly_heatmap_rows,
)
