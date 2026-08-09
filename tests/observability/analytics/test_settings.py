# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Where the parsed knobs are bound, under the names the tree reads them by."""
from __future__ import annotations

import unittest
from pathlib import Path

from orchestrator.observability.analytics import settings as analytics_settings
from tests.observability.analytics.analytics_reload_helpers import reload_analytics as _reload

_ANALYTICS_LOG_PATH = "ANALYTICS_LOG_PATH"

_ANALYTICS_RETENTION_DAYS = "ANALYTICS_RETENTION_DAYS"

_ANALYTICS_DB_URL = "ANALYTICS_DB_URL"

_TRACK_SKILL_TRIGGERS = "TRACK_SKILL_TRIGGERS"

_TRAJECTORY_LOG_PATH = "TRAJECTORY_LOG_PATH"

_TRAJECTORY_RETENTION_DAYS = "TRAJECTORY_RETENTION_DAYS"

# The six knobs, which are the whole surface this owner answers for.
_KNOBS = (
    _ANALYTICS_LOG_PATH,
    _ANALYTICS_RETENTION_DAYS,
    _ANALYTICS_DB_URL,
    _TRACK_SKILL_TRIGGERS,
    _TRAJECTORY_LOG_PATH,
    _TRAJECTORY_RETENTION_DAYS,
)

_EXPLICIT_LOG_PATH = "/var/log/orch/a.jsonl"

_EXPLICIT_TRAJECTORY_PATH = "/var/log/orch/t.jsonl"

_DB_URL = "postgresql://u:p@db.example.com:5432/orchestrator_analytics"

_DEFAULT_RETENTION_DAYS = 90

_KEEP_FOREVER = "0"


class BoundKnobTest(unittest.TestCase):
    """The holder binds every knob the environment implies, under the name the
    whole tree reads it back by.
    """

    def test_the_environment_lands_on_every_knob(self) -> None:
        _reload({
            _ANALYTICS_LOG_PATH: _EXPLICIT_LOG_PATH,
            _ANALYTICS_DB_URL: _DB_URL,
            _TRACK_SKILL_TRIGGERS: "1",
            _TRAJECTORY_LOG_PATH: _EXPLICIT_TRAJECTORY_PATH,
            _TRAJECTORY_RETENTION_DAYS: _KEEP_FOREVER,
        })
        bound = {
            name: getattr(analytics_settings, name) for name in _KNOBS
        }
        self.assertEqual(
            bound,
            {
                _ANALYTICS_LOG_PATH: Path(_EXPLICIT_LOG_PATH),
                _ANALYTICS_RETENTION_DAYS: _DEFAULT_RETENTION_DAYS,
                _ANALYTICS_DB_URL: _DB_URL,
                _TRACK_SKILL_TRIGGERS: True,
                _TRAJECTORY_LOG_PATH: Path(_EXPLICIT_TRAJECTORY_PATH),
                _TRAJECTORY_RETENTION_DAYS: 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
