# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical required-condition import site, answered by the query owner.

Each name is bound to the owner's own function, so the side a condition is
spliced onto -- and the event filter that leaves a view-backed read no rows --
are decided in one place whichever module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.conditions import (
    agent_event_excluded as _agent_event_excluded,
    append_where_condition as _append_where_condition,
    prepend_where_condition as _prepend_where_condition,
)


_COMPATIBILITY_EXPORTS = (
    _agent_event_excluded,
    _append_where_condition,
    _prepend_where_condition,
)
