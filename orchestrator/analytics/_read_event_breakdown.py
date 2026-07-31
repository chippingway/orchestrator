# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical event-count import site, answered by the query owner.

The name is bound to the owner's own function, so the table the counts are
scanned off and the tie-break that keeps them stable are the same whichever
module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.event_breakdowns import (
    event_breakdown_rows as _event_breakdown_rows,
)


_COMPATIBILITY_EXPORTS = (
    _event_breakdown_rows,
)
