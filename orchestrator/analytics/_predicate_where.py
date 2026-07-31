# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical window-predicate import site, answered by the query owner.

Each name is bound to the owner's own object, so the clause a caller builds
here is the clause the read families build, against the same three tables.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.predicates import (
    DAILY_ROLLUP_VIEW as _DAILY_ROLLUP_VIEW,
    build_rollup_window_where as _build_rollup_window_where,
    build_view_window_where as _build_view_window_where,
    build_where as _build_where,
    build_window_where as _build_window_where,
    day_bound as _day_bound,
)


_COMPATIBILITY_EXPORTS = (
    _DAILY_ROLLUP_VIEW,
    _build_rollup_window_where,
    _build_view_window_where,
    _build_where,
    _build_window_where,
    _day_bound,
)
