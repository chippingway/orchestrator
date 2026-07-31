# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical token-share import site, answered by the query owner.

The three fragments are the owner's own strings, so the denominator a cache
share is weighted by cannot differ between a caller naming this module and the
projection that splices it into a scan.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.cache_shares import (
    ROLLUP_ALL_TOKENS_SQL as _ROLLUP_ALL_TOKENS_SQL,
    ROLLUP_CACHE_FRACTION_SQL as _ROLLUP_CACHE_FRACTION_SQL,
    ROLLUP_CACHE_TOKENS_SQL as _ROLLUP_CACHE_TOKENS_SQL,
)


_COMPATIBILITY_EXPORTS = (
    _ROLLUP_ALL_TOKENS_SQL,
    _ROLLUP_CACHE_FRACTION_SQL,
    _ROLLUP_CACHE_TOKENS_SQL,
)
