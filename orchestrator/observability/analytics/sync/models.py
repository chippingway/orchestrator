# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one replay is counted by, and the state its loop carries between lines.

The result a caller reads back is frozen and the tallies behind it are not:
they are accumulated on a counters object rather than in `nonlocal` locals, so
every step of the ingest stays a module-scope function that can be driven on
its own, and they are folded into the frozen result once the run returns. The
context beside them is what does not change between lines -- the file being
read, the statement its rows are sent under, and the clock the progress records
are measured against -- so a per-line helper is handed one object instead of
six arguments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class SyncResult:
    """Counts returned by `sync_jsonl_to_postgres`.

    - `inserted` -- records that hit the database as a new row.
    - `skipped_duplicate` -- records whose `content_hash` already
      existed; the `ON CONFLICT DO NOTHING` path absorbed them.
    - `skipped_malformed` -- lines that were blank, unparseable JSON,
      not a JSON object, or missing one of `ts` / `repo` / `issue` /
      `event`. The line number is logged as a warning so the operator
      can clean them up out-of-band; the sync never deletes or rewrites
      the JSONL file itself.
    - `total_lines` -- raw line count consumed from the file
      (including blanks), so the caller can sanity-check progress.
    - `duration_s` -- wall-clock seconds from connect entry through
      commit / close, rounded to 3 decimals. Lets the CLI surface a
      human-readable elapsed time without re-timing externally; the
      no-op paths (URL unset / file absent) return 0.0.
    """

    inserted: int = 0
    skipped_duplicate: int = 0
    skipped_malformed: int = 0
    total_lines: int = 0
    malformed_line_numbers: tuple[int, ...] = field(default_factory=tuple)
    duration_s: float = field(default_factory=float)


@dataclass
class SyncCounters:
    """Mutable tallies threaded through the ingest loop.

    `ingest_records`, `flush_batch`, and `note_malformed_line` update these in
    place, which is what lets each of them live at module scope and be
    unit-tested on its own. The final counts are folded into the frozen
    `SyncResult` once the sync returns.
    """

    inserted: int = 0
    skipped_duplicate: int = 0
    skipped_malformed: int = 0
    total_lines: int = 0
    malformed_lines: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class IngestContext:
    """Stable inputs and mutable counters shared by one ingest pass."""

    log_path: Path
    insert_sql: str
    source_path: Optional[str]
    json_adapter: Callable[[Any], Any]
    counters: SyncCounters
    start: float
