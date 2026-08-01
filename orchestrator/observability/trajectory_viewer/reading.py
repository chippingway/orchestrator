# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one read of the trajectory file comes back with, and what it survives.

The file is append-only JSONL, written a line at a time by whichever
orchestrator version was running, and an operator opening the page has to see
whatever is in it. So a blank line, a line that is not JSON, and a record
belonging to another producer are each skipped rather than raised over: one
hand-edited or half-written entry costs its own row instead of the whole view.

Runs come back newest first, and the position a line was counted off with is
the tiebreak. Timestamps are second-precision, so two records of the same
second have no order of their own -- but the file is append-only, which makes
the one appended later the more recent, and that is the order the page shows
them in.

The two ways a read fails part company on purpose. A missing file is what a
sink switched on but not yet written to looks like, so it answers empty and
silently. Every other `OSError` is warned about first -- on the
`orchestrator.trajectory_reader` logger, the name an operator's filter is keyed
on, whichever module the read is reached through -- and then answers empty too,
because a page that stays up showing nothing is what an unreadable file should
cost.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from orchestrator.observability.trajectory_viewer import parsing
from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun


log = logging.getLogger("orchestrator.trajectory_reader")


def parse_trajectory_line(line: str, *, sequence: int) -> Optional[TrajectoryRun]:
    if not line.strip():
        return None
    try:
        record_object = json.loads(line)
    except json.JSONDecodeError:
        return None
    return parsing.parse_record(record_object, sequence=sequence)


def read_trajectory_file(path: Path) -> list[TrajectoryRun]:
    runs: list[TrajectoryRun] = []
    with path.open("r", encoding="utf-8") as trajectory_file:
        for sequence, line in enumerate(trajectory_file):
            run = parse_trajectory_line(line, sequence=sequence)
            if run is not None:
                runs.append(run)
    return runs


def read_trajectories(log_path: Optional[Path]) -> list[TrajectoryRun]:
    if log_path is None:
        return []
    try:
        runs = read_trajectory_file(log_path)
    except FileNotFoundError:
        return []
    except OSError as error:
        log.warning("could not read trajectory log %s: %s", log_path, error)
        return []
    runs.sort(key=run_sort_key, reverse=True)
    return runs


def run_sort_key(run: TrajectoryRun) -> tuple[str, int]:
    return run.ts, run.seq
