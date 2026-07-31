# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The trajectory sink's append entry point.

What a caller outside one tracked agent run reaches: the append the analytics
package republishes as `append_trajectory_record`. It takes the trajectory
sink's own lock -- never the analytics sink's -- so the trajectory file's
append-during-prune race is closed without the two files serializing against
one another.

This owner sits above the recorders rather than beside the record builders
below it: it resolves *which* trajectory file a bare append writes to, and the
answer is the settings holder captured by the `events` owner it was imported
alongside. The analytics package bootstrap rebuilds both together for each
instance it initializes, so an append taken off one instance keeps writing
where that instance was configured to. The lock deliberately does not live
here for that same reason -- it is minted on the `io` owner, which is loaded
once per process, so an append held across a rebuild still serializes against
the prune.
"""

from __future__ import annotations

from orchestrator.observability.analytics import config as analytics_config
from orchestrator.observability.analytics.recording.events import settings_holder
from orchestrator.observability.analytics.recording.io import (
    TRAJECTORY_FILE_LOCK,
    append_jsonl_record,
)


def append_trajectory_record(record: dict) -> None:
    """Append one JSONL line to the configured trajectory sink."""
    append_jsonl_record(
        analytics_config.settings_on(settings_holder()).trajectory_log_path,
        TRAJECTORY_FILE_LOCK,
        record,
    )
