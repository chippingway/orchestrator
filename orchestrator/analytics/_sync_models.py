# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for what one replay is counted by.

The result a caller reads back keeps its public spelling and the two the ingest
loop threads keep the private ones they were published under, so a caller
naming either module lands on the object a run actually accumulates into.
"""

from __future__ import annotations

from orchestrator.observability.analytics.sync.models import (
    IngestContext as _IngestContext,
    SyncCounters as _SyncCounters,
    SyncResult as SyncResult,
)

_COMPATIBILITY_EXPORTS = (
    SyncResult,
    _SyncCounters,
    _IngestContext,
)
