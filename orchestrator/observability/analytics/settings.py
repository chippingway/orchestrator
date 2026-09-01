# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The six knobs as parsed for this process, and where a caller patches one.

One settings holder for both sinks, the retention prunes, and the Postgres
surfaces: the values `config` parses out of the environment, bound once at this
module's import under the names the whole analytics tree reads them back by.
Binding them here rather than re-reading the environment per call is the
environment contract an operator has -- a knob takes effect when the process
starts, and a value patched on this module is what every read after it
observes.

This is the one module under the analytics owners that reaches
`orchestrator.config`, because the default analytics sink lives under its
`LOG_DIR`. Nothing on the recording path imports it: `config.live_settings`
names it inside the call, so a producer that appends a record pays for the
process configuration when it writes rather than when it imports.
"""

from __future__ import annotations

from pathlib import Path

from orchestrator.observability.analytics import config as analytics_config

ANALYTICS_LOG_PATH: Path | None = analytics_config.parse_log_path()

ANALYTICS_RETENTION_DAYS: int = analytics_config.parse_retention_days()

ANALYTICS_DB_URL: str | None = analytics_config.parse_db_url()

TRACK_SKILL_TRIGGERS: bool = analytics_config.parse_track_skill_triggers()

TRAJECTORY_LOG_PATH: Path | None = analytics_config.parse_trajectory_log_path()

TRAJECTORY_RETENTION_DAYS: int = analytics_config.parse_trajectory_retention_days()
