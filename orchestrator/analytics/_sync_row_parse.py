# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the record parse, answered by its owner.

The seven names are the owner's own functions, so the encoding a content hash
is taken over and the coercion each required field is narrowed by are decided
once whichever module a caller names.
"""

from __future__ import annotations

from orchestrator.observability.analytics.sync.records import (
    canonical_json as _canonical_json,
    content_hash as _content_hash,
    extra_columns as _extra_columns,
    issue_number as _issue_number,
    parse_ts as _parse_ts,
    required_columns as _required_columns,
    required_text as _required_text,
)

_COMPATIBILITY_EXPORTS = (
    _canonical_json,
    _content_hash,
    _extra_columns,
    _issue_number,
    _parse_ts,
    _required_columns,
    _required_text,
)
