# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Where the parsed knobs are bound, and what still reads them off it."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

from orchestrator.observability.analytics import settings as analytics_settings
from tests.analytics_reload_helpers import reload_analytics as _reload

_ANALYTICS_PACKAGE = "orchestrator.analytics"

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

# A path no read here ever opens; only which value comes back matters.
_PROBE_PATH = Path("/tmp/orchestrator-analytics-settings-probe")


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

class ForwardedKnobTest(unittest.TestCase):
    """The flat analytics package answers with what is patched on the holder,
    so a caller still reading a knob through the historical spelling and the
    owners that write the sinks cannot disagree about it.
    """

    def test_a_patched_knob_reaches_the_package(self) -> None:
        package = import_module(_ANALYTICS_PACKAGE)
        with patch.object(analytics_settings, _TRAJECTORY_LOG_PATH, _PROBE_PATH):
            self.assertEqual(package.TRAJECTORY_LOG_PATH, _PROBE_PATH)
        self.assertIsNone(package.TRAJECTORY_LOG_PATH)

    def test_every_knob_is_published(self) -> None:
        package = import_module(_ANALYTICS_PACKAGE)
        for name in _KNOBS:
            with self.subTest(name=name):
                self.assertIn(name, package.__all__)
                self.assertEqual(
                    getattr(package, name), getattr(analytics_settings, name),
                )

    def test_the_configuration_module_forwards(self) -> None:
        # The one historical name that is a module rather than a knob.
        self.assertIs(
            import_module(_ANALYTICS_PACKAGE).config,
            import_module("orchestrator.config"),
        )


if __name__ == "__main__":
    unittest.main()
