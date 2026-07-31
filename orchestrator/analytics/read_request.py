# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical request-binding import site, answered by the query owner.

The signatures are the owner's own `Signature` objects and the binder is its
own function, so a keyword call bound through this module is bound by the same
vocabulary the read families are built on.
"""

from __future__ import annotations

# Twelve names off one owner, split into the signatures and the binder beside
# them so neither statement passes the eight-name import ceiling.
from orchestrator.observability.analytics.query.requests import (
    FILTERED_READ_SIGNATURE as FILTERED_READ_SIGNATURE,
    HEATMAP_SIGNATURE as HEATMAP_SIGNATURE,
    ISSUE_EVENTS_SIGNATURE as ISSUE_EVENTS_SIGNATURE,
    ISSUES_SIGNATURE as ISSUES_SIGNATURE,
    LIMITED_READ_SIGNATURE as LIMITED_READ_SIGNATURE,
    RECENT_EXITS_SIGNATURE as RECENT_EXITS_SIGNATURE,
    SOURCE_READ_SIGNATURE as SOURCE_READ_SIGNATURE,
)
from orchestrator.observability.analytics.query.requests import (
    LIMIT_FIELD as LIMIT_FIELD,
    RECENT_EXIT_LIMIT as RECENT_EXIT_LIMIT,
    bind_read_request as bind_read_request,
    resolve_read_query as resolve_read_query,
    window_filters as window_filters,
)


_COMPATIBILITY_EXPORTS = (
    FILTERED_READ_SIGNATURE,
    HEATMAP_SIGNATURE,
    ISSUE_EVENTS_SIGNATURE,
    ISSUES_SIGNATURE,
    LIMIT_FIELD,
    LIMITED_READ_SIGNATURE,
    RECENT_EXIT_LIMIT,
    RECENT_EXITS_SIGNATURE,
    SOURCE_READ_SIGNATURE,
    bind_read_request,
    resolve_read_query,
    window_filters,
)
