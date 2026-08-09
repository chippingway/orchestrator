# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The trajectory sink's append entry point.

What a caller outside one tracked agent run reaches, and what the flat
analytics package forwards `append_trajectory_record` to. It takes the
trajectory sink's own lock -- never the analytics sink's -- so the trajectory
file's append-during-prune race is closed without the two files serializing
against one another.

Which trajectory file it writes to is read off the `settings` holder inside
the call, so a bare append and the by-age prune that rewrites the file under
it resolve the same knob. The lock deliberately does not live here -- it is
minted on the `sink` owner beside the analytics sink's, so this append and
that prune hold one object.
"""

from __future__ import annotations

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics.sink import (
    TRAJECTORY_FILE_LOCK,
    append_jsonl_record,
)


def append_trajectory_record(record: dict) -> None:
    """Append one JSONL line to the configured trajectory sink."""
    append_jsonl_record(
        analytics_config.live_settings().trajectory_log_path,
        TRAJECTORY_FILE_LOCK,
        record,
    )
