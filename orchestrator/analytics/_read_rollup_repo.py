# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical repo / throughput import site, answered by the query owners.

The five names are the two owners' own objects, so the terminal stages a day's
throughput is counted over -- and the short circuits a narrowed selection
falls to -- are decided once whichever module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.repo_breakdowns import (
    repo_breakdown_rows as _repo_breakdown_rows,
)
from orchestrator.observability.analytics.query.throughput_days import (
    THROUGHPUT_RESOLVED_STAGES as _THROUGHPUT_RESOLVED_STAGES,
    selected_throughput_stages as _selected_throughput_stages,
    throughput_from_row as _throughput_from_row,
    throughput_rows as _throughput_rows,
)


_COMPATIBILITY_EXPORTS = (
    _THROUGHPUT_RESOLVED_STAGES,
    _repo_breakdown_rows,
    _selected_throughput_stages,
    _throughput_from_row,
    _throughput_rows,
)
