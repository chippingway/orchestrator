# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical predicate-state import site, answered by the query owner.

Both names are bound to the owner's own class, so a filter set built through
this module is the one every read family projects onto.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.filters import (
    WhereBuilder as _WhereBuilder,
    WindowFilters as _WindowFilters,
)


_COMPATIBILITY_EXPORTS = (
    _WhereBuilder,
    _WindowFilters,
)
