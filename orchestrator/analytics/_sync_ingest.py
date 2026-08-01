# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the batched ingest and its accounting.

The eight names are the owner's own, including the default buffer size: the
loop reads that size off its owner when a pass starts, so the value bound here
reports what the ingest is running with rather than deciding it.
"""

from __future__ import annotations

from orchestrator.observability.analytics.sync.ingest import (
    BATCH_SIZE as _BATCH_SIZE,
    RecordIngester as _RecordIngester,
    emit_progress as _emit_progress,
    existing_hashes as _existing_hashes,
    flush_batch as _flush_batch,
    ingest_records as _ingest_records,
    note_malformed_line as _note_malformed_line,
    stream_records as _stream_records,
)

_COMPATIBILITY_EXPORTS = (
    _BATCH_SIZE,
    _emit_progress,
    _flush_batch,
    _note_malformed_line,
    _existing_hashes,
    _RecordIngester,
    _stream_records,
    _ingest_records,
)
