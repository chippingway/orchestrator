# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Serialized JSONL append shared by the analytics and trajectory sinks.

One owner for how a record reaches disk, so the two sinks cannot disagree
about it: the same encoding, the same locking discipline, and the same
fail-open answer to a filesystem that refuses the write. *Which* file a record
is written to is the caller's, which is why the path arrives as an argument
rather than being read here; the trajectory sink still brings its own lock
along with it until it has an owner beside this one.

The analytics sink's lock is minted here rather than beside the recorders
because this owner is loaded once per process while `events` is rebuilt for
each analytics package instance. Two things have to take the same lock object
for the sink to be safe -- the append and the retention prune that rewrites
the file under it -- and a lock recreated with the recorders would leave any
reference taken before a rebuild serializing against nothing, which is exactly
the append-during-prune race the lock exists to close.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

ANALYTICS_FILE_LOCK = threading.Lock()


def append_jsonl_record(path: Optional[Path], lock: threading.Lock, record: dict) -> None:
    """Append one JSONL line to `path` under `lock`; no-op when `path` is
    None.

    Shared core for the analytics and trajectory sinks: each passes its
    own path and dedicated lock so the two files never serialize against
    one another. OSError is logged and swallowed so a misconfigured path
    (read-only mount, disk full, permission failure) cannot stop the
    per-issue tick from making progress.

    Holds `lock` around the actual filesystem ops so a concurrent prune
    cannot rewrite the file (via `os.replace`) between this append's open
    and write; otherwise the appended record would be written to the
    soon-unlinked inode and silently lost. Scheduler workers fan out
    across threads in the same process, so the race is real on the
    multi-issue path. JSON serialization is done outside the lock to keep
    the critical section short.
    """
    if path is None:
        return
    serialized = f"{json.dumps(record, sort_keys=True)}\n"
    try:
        with lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(serialized)
    except OSError as error:
        from orchestrator.observability.analytics.recording import events

        events.log.warning("could not write record to %s: %s", path, error)
