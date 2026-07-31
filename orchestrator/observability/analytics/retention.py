# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The by-age prune that keeps both JSONL sinks bounded.

Three entry points, one per caller: the polling tick's fail-open wrapper, the
analytics sink's prune, and the trajectory sink's. The two sinks are pruned
separately all the way down -- each reads its own path and retention knob, and
each takes its own lock -- so an operator can keep trajectories for a week and
analytics for a year, and neither file's rewrite ever blocks on the other's
append. The scan and rewrite steps beneath them are shared, which is what keeps
the two answering the same way about a malformed line or a full disk.

This owner sits above the recorders rather than beside the scan and rewrite
leaves below it, for the same reason the trajectory sink's ``api`` does: it
resolves *which* files a bare prune rewrites, and the answer is the settings
holder captured by the ``events`` owner it was imported alongside. The analytics
package bootstrap rebuilds both together for each instance it initializes, so a
prune taken off one instance keeps rewriting what that instance was configured
with. The locks deliberately do not live here -- they are minted on the ``io``
owner, which is loaded once per process, so an append held across a rebuild
still serializes against the rewrite happening under it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics.recording.events import (
    log,
    settings_holder,
)
from orchestrator.observability.analytics.recording.io import (
    ANALYTICS_FILE_LOCK,
    TRAJECTORY_FILE_LOCK,
)
from orchestrator.observability.analytics.retention_rewrite import (
    prune_jsonl_records,
)


def prune_with_retention_logging() -> None:
    """Drop analytics records past `ANALYTICS_RETENTION_DAYS` and log the
    outcome. Intended for the per-tick caller in `main._run_tick`.

    A no-op when the sink is disabled or retention is non-positive (the
    documented "keep raw data indefinitely" knob); `prune_old_records`
    itself handles the absent-file / unparseable-line / IO-failure cases.
    A runaway programming error here must not abort the polling loop --
    analytics is observability, never authoritative workflow state -- so
    any escape is logged and swallowed. Per-tick cadence is cheap: the
    helper reads the file at most once and only rewrites it when at
    least one record is older than the retention window.

    Delegates through the settings holder
    (`settings_holder().prune_old_records()`) so the call stays
    interceptable via `patch.object(analytics, "prune_old_records", ...)`.
    """
    try:
        removed = settings_holder().prune_old_records()
    except Exception:
        log.exception("analytics retention prune raised; continuing")
        return
    if removed:
        log.info("analytics retention prune removed %d record(s)", removed)


def prune_old_records(*, now: Optional[datetime] = None) -> int:
    """Remove records whose `ts` is older than `ANALYTICS_RETENTION_DAYS`.

    Reads the `ANALYTICS_LOG_PATH` / `ANALYTICS_RETENTION_DAYS` bound on the
    `orchestrator.analytics` settings holder (parsed from the env at import).

    Returns the number of records removed. No-op (returns 0) when the
    sink is disabled, retention is non-positive (keep forever), or the
    file does not exist yet. `now` defaults to the current UTC time and
    is parameter-overridable so tests can pin the comparison point.

    Records whose `ts` is missing, not a string, or unparseable are
    preserved verbatim -- the prune step does not silently drop malformed
    data; an operator can clean it up. Likewise lines that are not valid
    JSON survive the rewrite.

    The rewrite goes through a temp file in the same directory followed
    by `os.replace` so a crash mid-prune cannot truncate the analytics
    file.

    Holds `ANALYTICS_FILE_LOCK` across the read + rewrite so a concurrent
    `append_record` cannot land between the read and the `os.replace`
    -- without this, an append that observed the old inode after we
    read but before `os.replace` would write to the soon-unlinked inode
    and be silently lost. Scheduler workers may still be running when
    the polling loop calls this between ticks, so serializing with
    `append_record` is what keeps that prune-window invisible.
    """
    settings = analytics_config.settings_on(settings_holder())
    return prune_jsonl_records(
        settings.log_path,
        settings.retention_days,
        ANALYTICS_FILE_LOCK,
        now,
    )


def prune_trajectory_records(*, now: Optional[datetime] = None) -> int:
    """Remove trajectory records older than `TRAJECTORY_RETENTION_DAYS`.

    Reads the `TRAJECTORY_LOG_PATH` / `TRAJECTORY_RETENTION_DAYS` bound on
    the `orchestrator.analytics` settings holder. Mirrors `prune_old_records`
    exactly (no-op when the sink is disabled, retention is non-positive, or
    the file is absent; malformed / unparseable lines preserved; atomic
    temp-file + `os.replace` rewrite) but operates solely on the
    trajectory file under `TRAJECTORY_FILE_LOCK` -- it never touches
    `ANALYTICS_LOG_PATH`, the analytics Postgres sync, or the dashboard
    rollups. `now` is parameter-overridable so tests can pin the
    comparison point.
    """
    settings = analytics_config.settings_on(settings_holder())
    return prune_jsonl_records(
        settings.trajectory_log_path,
        settings.trajectory_retention_days,
        TRAJECTORY_FILE_LOCK,
        now,
    )
