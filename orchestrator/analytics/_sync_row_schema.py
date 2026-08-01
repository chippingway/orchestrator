# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the column inventory, answered by its owner.

The seven names are the owner's own constants, so what a record must carry,
what the table has a column for, and which of those columns hold JSON read the
same whichever module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.sync.columns import (
    COL_EVENT as _COL_EVENT,
    COL_ISSUE as _COL_ISSUE,
    COL_REPO as _COL_REPO,
    COL_TS as _COL_TS,
    JSONB_COLUMNS as _JSONB_COLUMNS,
    PROMOTED_COLUMNS as _PROMOTED_COLUMNS,
    REQUIRED_KEYS as _REQUIRED_KEYS,
)

_COMPATIBILITY_EXPORTS = (
    _COL_EVENT,
    _COL_ISSUE,
    _COL_REPO,
    _COL_TS,
    _JSONB_COLUMNS,
    _PROMOTED_COLUMNS,
    _REQUIRED_KEYS,
)
