# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the whole row translation, across three owners.

The twenty names are the union the three flat leaves beside this one publish,
grouped here the way a caller already imports them: a caller that named this
module and a caller that named a leaf land on the same objects, which is what
keeps the column inventory, the content hash, and the INSERT from drifting
apart between them.
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
from orchestrator.observability.analytics.sync.records import (
    canonical_json as _canonical_json,
    content_hash as _content_hash,
    extra_columns as _extra_columns,
    issue_number as _issue_number,
    parse_ts as _parse_ts,
    required_columns as _required_columns,
    required_text as _required_text,
)
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
    _canonical_json,
    _content_hash,
    _extra_columns,
    _issue_number,
    _parse_ts,
    _required_columns,
    _required_text,
    _COL_EVENT,
    _COL_ISSUE,
    _COL_REPO,
    _COL_TS,
    _JSONB_COLUMNS,
    _PROMOTED_COLUMNS,
    _REQUIRED_KEYS,
)
