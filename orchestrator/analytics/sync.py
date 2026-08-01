# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site and `-m` target for the analytics sync.

`python -m orchestrator.analytics.sync` still starts a replay, and every name
the sync ever published is still resolvable here, so an operator's scheduled
command and a caller that imported one of those names both keep landing on what
the run uses. Nothing is implemented here: the command lives on
`observability/analytics/sync/cli.py` and the replay under it on that package's
other owners, and each name below binds the owner's own object rather than a
copy of it.
"""

from __future__ import annotations

import sys

from orchestrator.observability.analytics.sync.cli import (
    cli_parser as _cli_parser,
    configure_cli_logging as _configure_cli_logging,
    log as log,
    main as main,
    print_cli_result as _print_cli_result,
    run_cli as _run_cli,
)
from orchestrator.observability.analytics.sync.database import (
    DAILY_ROLLUP_VIEW as _DAILY_ROLLUP_VIEW,
    close_quietly as _close_quietly,
    default_connect as _default_connect,
    default_json_adapter as _default_json_adapter,
    execute_rollup_refresh as _execute_rollup_refresh,
    refresh_daily_rollup as _refresh_daily_rollup,
    rollback_quietly as _rollback_quietly,
)
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
from orchestrator.observability.analytics.sync.models import (
    IngestContext as _IngestContext,
    SyncCounters as _SyncCounters,
    SyncResult as SyncResult,
)
from orchestrator.observability.analytics.sync.redaction import (
    redact_db_url as _redact_db_url,
    redacted_netloc as _redacted_netloc,
    redacted_query as _redacted_query,
)
from orchestrator.observability.analytics.sync.rows import (
    RowProvenance as _RowProvenance,
    build_insert_sql as _build_insert_sql,
    prepare_record as _prepare_record,
    row_values as _row_values,
)
from orchestrator.observability.analytics.sync.run import (
    SyncRequest as _SyncRequest,
    SyncRun as _SyncRun,
    sync_jsonl_to_postgres as sync_jsonl_to_postgres,
)

# A progress record drops per flush, so the interval a caller reads off this
# module is the buffer size the ingest is running with.
_PROGRESS_INTERVAL = _BATCH_SIZE

_COMPATIBILITY_EXPORTS = (
    _cli_parser,
    _configure_cli_logging,
    _print_cli_result,
    _run_cli,
    _DAILY_ROLLUP_VIEW,
    _close_quietly,
    _default_connect,
    _default_json_adapter,
    _execute_rollup_refresh,
    _refresh_daily_rollup,
    _rollback_quietly,
    _BATCH_SIZE,
    _RecordIngester,
    _emit_progress,
    _existing_hashes,
    _flush_batch,
    _ingest_records,
    _note_malformed_line,
    _stream_records,
    _IngestContext,
    _SyncCounters,
    _redact_db_url,
    _redacted_netloc,
    _redacted_query,
    _RowProvenance,
    _build_insert_sql,
    _prepare_record,
    _row_values,
    _SyncRequest,
    _SyncRun,
)

if __name__ == "__main__":
    sys.exit(main())
