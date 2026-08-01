# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the row mapping, answered by its owner.

The six names are the owner's own objects, so the statement a batch is sent
under, the tuple that fills it, and the reason a line is skipped for are
decided once whichever module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.sync.rows import (
    PreparedRecord as _PreparedRecord,
    RowProvenance as _RowProvenance,
    build_insert_sql as _build_insert_sql,
    prepare_record as _prepare_record,
    row_values as _row_values,
    split_row as _split_row,
)

_COMPATIBILITY_EXPORTS = (
    _PreparedRecord,
    _RowProvenance,
    _build_insert_sql,
    _prepare_record,
    _row_values,
    _split_row,
)
