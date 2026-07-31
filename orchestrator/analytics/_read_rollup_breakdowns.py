# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical stage / backend rollup import site, answered by the query owners.

The six names are the two owners' own functions, so the cache split a stage
panel stacks and the pinned agent-exit scope a backend comparison is read under
are decided once whichever module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.backend_efficiency import (
    backend_efficiency_from_row as _backend_efficiency_from_row,
    backend_efficiency_rows as _backend_efficiency_rows,
    backend_efficiency_sql as _backend_efficiency_sql,
)
from orchestrator.observability.analytics.query.stage_breakdowns import (
    stage_breakdown_from_row as _stage_breakdown_from_row,
    stage_breakdown_rows as _stage_breakdown_rows,
    stage_breakdown_sql as _stage_breakdown_sql,
)


_COMPATIBILITY_EXPORTS = (
    _backend_efficiency_from_row,
    _backend_efficiency_rows,
    _backend_efficiency_sql,
    _stage_breakdown_from_row,
    _stage_breakdown_rows,
    _stage_breakdown_sql,
)
