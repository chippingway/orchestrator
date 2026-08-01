# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the resolved request and the run over it.

Both names are the owner's own, so what a request falls back to when a caller
omits an input, and the transaction shape the replay is wrapped in, are read
here exactly as the service entry point drives them.
"""

from __future__ import annotations

from orchestrator.observability.analytics.sync.run import (
    SyncRequest as _SyncRequest,
    SyncRun as _SyncRun,
)

_COMPATIBILITY_EXPORTS = (
    _SyncRequest,
    _SyncRun,
)
