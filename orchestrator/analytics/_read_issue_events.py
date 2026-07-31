# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical event-trace import site, answered by the query owner.

Both names are bound to the owner's own functions, so the `(repo, issue)` pair
spliced ahead of the generated predicate and the `id` tie-break that orders two
events recorded in the same instant hold whichever module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.issue_events import (
    issue_event_from_row as _issue_event_from_row,
    issue_event_rows as _issue_event_rows,
)


_COMPATIBILITY_EXPORTS = (
    _issue_event_from_row,
    _issue_event_rows,
)
