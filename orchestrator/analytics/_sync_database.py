# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the connection and the rollup refresh.

The two adapters a run may be given instead of, the two quiet cleanups it ends
on, and the refresh it leaves behind are the owner's own, so the view named
here is the view the statement rebuilds.
"""

from __future__ import annotations

from orchestrator.observability.analytics.sync.database import (
    DAILY_ROLLUP_VIEW as _DAILY_ROLLUP_VIEW,
    close_quietly as _close_quietly,
    default_connect as _default_connect,
    default_json_adapter as _default_json_adapter,
    execute_rollup_refresh as _execute_rollup_refresh,
    refresh_daily_rollup as _refresh_daily_rollup,
    rollback_quietly as _rollback_quietly,
)

_COMPATIBILITY_EXPORTS = (
    _DAILY_ROLLUP_VIEW,
    _default_connect,
    _default_json_adapter,
    _rollback_quietly,
    _close_quietly,
    _execute_rollup_refresh,
    _refresh_daily_rollup,
)
