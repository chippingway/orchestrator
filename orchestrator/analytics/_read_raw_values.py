# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical raw-coercion import site, answered by the query owner.

The five names are bound to the owner's own functions, so what a NULL column
reads back as -- and what a cleared multiselect is told apart from an
unfiltered one by -- is decided once whichever module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.raw_values import (
    bool_or_none as _bool_or_none,
    empty_filter_selected as _empty_filter_selected,
    float_or_none as _float_or_none,
    int_or_none as _int_or_none,
    row_int as _row_int,
)


_COMPATIBILITY_EXPORTS = (
    _bool_or_none,
    _empty_filter_selected,
    _float_or_none,
    _int_or_none,
    _row_int,
)
