# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One replay, from what it was asked for to what it hands back.

`sync_jsonl_to_postgres` is the whole service surface: resolve the request,
answer a configured no-op without opening anything, and otherwise run it. The
source and the destination are the caller's own values or the two knobs, read
live rather than bound at import so they follow whichever environment the
caller set up; the connection factory and the JSON adapter are the caller's own
or the defaults, which is what lets a whole run be driven over a connection of
its own with no driver installed.

Three configured states are a no-op rather than a failure: the sink disabled,
the database URL unset, and a JSONL file that does not exist yet. Each is
logged and returns empty counts, because the sync is scheduled by an operator
who may not have deployed Postgres, and a run that found nothing to do is not
an error.

What a real run guarantees is the transaction shape around the ingest: a
driver error rolls back and propagates so the CLI exits non-zero rather than
reporting success on a half-inserted batch, the connection is closed either
way, and a successful commit is always followed by the rollup refresh --
including for a run that inserted nothing, since rerunning the sync is the
documented recovery path for a rollup left behind by an earlier failed refresh.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics.sync.database import (
    close_quietly,
    default_connect,
    default_json_adapter,
    refresh_daily_rollup,
    rollback_quietly,
)
from orchestrator.observability.analytics.sync.ingest import ingest_records
from orchestrator.observability.analytics.sync.models import (
    IngestContext,
    SyncCounters,
    SyncResult,
)
from orchestrator.observability.analytics.sync.redaction import redact_db_url
from orchestrator.observability.analytics.sync.rows import build_insert_sql

log = logging.getLogger("orchestrator.analytics.sync")


@dataclass(frozen=True)
class SyncRequest:
    """Resolved source, destination, and injected adapters for one sync."""

    log_path: Path | None
    db_url: str | None
    connect_fn: Callable[[str], Any]
    json_adapter: Callable[[Any], Any]

    @classmethod
    def resolve(
        cls,
        log_path: Path | None,
        db_url: str | None,
        connect: Callable[[str], Any] | None,
        json_adapter: Callable[[Any], Any] | None,
    ) -> SyncRequest:
        settings = analytics_config.live_settings()
        return cls(
            log_path=(settings.log_path if log_path is None else log_path),
            db_url=(settings.db_url if db_url is None else db_url),
            connect_fn=connect or default_connect,
            json_adapter=json_adapter or default_json_adapter,
        )

    def ready(self) -> bool:
        """Log and reject configured no-op paths before any connection work."""
        if self.log_path is None:
            log.info("analytics_sync: ANALYTICS_LOG_PATH not configured; nothing to sync")
            return False
        if not self.db_url:
            log.info("analytics_sync: ANALYTICS_DB_URL not configured; nothing to sync")
            return False
        if not self.log_path.exists():
            log.info(
                "analytics_sync: %s does not exist yet; nothing to sync",
                self.log_path,
            )
            return False
        return True


@dataclass
class SyncRun:
    """Connection lifecycle, ingest state, and reporting for one replay."""

    request: SyncRequest
    counters: SyncCounters = field(default_factory=SyncCounters)
    start: float = field(default_factory=time.monotonic)

    def connect(self) -> Any:
        redacted_url = redact_db_url(self.request.db_url or "")
        log.info(
            "analytics_sync: connecting to %s (source=%s)",
            redacted_url,
            self.request.log_path,
        )
        conn = self.request.connect_fn(self.request.db_url)
        log.info(
            "analytics_sync: connection established to %s after %.3fs",
            redacted_url,
            time.monotonic() - self.start,
        )
        return conn

    def ingest_context(self) -> IngestContext:
        log_path = Path(self.request.log_path)
        return IngestContext(
            log_path=log_path,
            insert_sql=build_insert_sql(),
            source_path=str(log_path),
            json_adapter=self.request.json_adapter,
            counters=self.counters,
            start=self.start,
        )

    def commit(self, conn: Any) -> None:
        """Commit rows and refresh the rollup even for duplicate-only runs."""
        log.info(
            "analytics_sync: committing transaction (lines=%d inserted=%d duplicate=%d malformed=%d elapsed=%.3fs)",
            self.counters.total_lines,
            self.counters.inserted,
            self.counters.skipped_duplicate,
            self.counters.skipped_malformed,
            time.monotonic() - self.start,
        )
        conn.commit()
        refresh_daily_rollup(conn)

    def finalize(self) -> SyncResult:
        duration_s = round(time.monotonic() - self.start, 3)
        log.info(
            "analytics_sync: completed in %.3fs (inserted=%d duplicate=%d malformed=%d total_lines=%d source=%s)",
            duration_s,
            self.counters.inserted,
            self.counters.skipped_duplicate,
            self.counters.skipped_malformed,
            self.counters.total_lines,
            self.request.log_path,
        )
        return SyncResult(
            inserted=self.counters.inserted,
            skipped_duplicate=self.counters.skipped_duplicate,
            skipped_malformed=self.counters.skipped_malformed,
            total_lines=self.counters.total_lines,
            malformed_line_numbers=tuple(self.counters.malformed_lines),
            duration_s=duration_s,
        )

    def execute(self) -> SyncResult:
        conn = self.connect()
        try:
            self._ingest_and_commit(conn)
        except Exception:
            rollback_quietly(conn, "analytics_sync: rollback failed")
            raise
        finally:
            close_quietly(conn)
        return self.finalize()

    def _ingest_and_commit(self, conn: Any) -> None:
        ingest_records(conn, self.ingest_context())
        self.commit(conn)


def sync_jsonl_to_postgres(
    *,
    log_path: Path | None = None,
    db_url: str | None = None,
    connect: Callable[[str], Any] | None = None,
    json_adapter: Callable[[Any], Any] | None = None,
) -> SyncResult:
    """Replay the configured analytics JSONL records into Postgres."""
    request = SyncRequest.resolve(
        log_path,
        db_url,
        connect,
        json_adapter,
    )
    if not request.ready():
        return SyncResult()
    return SyncRun(request).execute()
