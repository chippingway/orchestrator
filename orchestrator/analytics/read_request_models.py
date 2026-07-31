# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical request-model import site, answered by the query owner.

The four models are the owner's own classes, so a request built through this
module is a request the read families accept.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.request_models import (
    ReadConnection as ReadConnection,
    ReadFilters as ReadFilters,
    ReadOptions as ReadOptions,
    ReadRequest as ReadRequest,
)


_COMPATIBILITY_EXPORTS = (
    ReadConnection,
    ReadFilters,
    ReadOptions,
    ReadRequest,
)
