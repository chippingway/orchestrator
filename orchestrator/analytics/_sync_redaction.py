# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the credential-safe URL rendering.

The two halves a libpq URL can hide credentials in, and the entry point over
both, are the owner's own -- so an endpoint logged through this module is
redacted exactly as the connect line is.
"""

from __future__ import annotations

from orchestrator.observability.analytics.sync.redaction import (
    redact_db_url as _redact_db_url,
    redacted_netloc as _redacted_netloc,
    redacted_query as _redacted_query,
)

_COMPATIBILITY_EXPORTS = (
    _redacted_netloc,
    _redacted_query,
    _redact_db_url,
)
