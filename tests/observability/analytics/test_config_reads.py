# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Tests for how an adapter reads an analytics knob back."""
from __future__ import annotations

import unittest
from importlib import import_module
from operator import attrgetter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from orchestrator.observability.analytics import config as analytics_config

_ANALYTICS_DB_URL = "ANALYTICS_DB_URL"

_TRAJECTORY_LOG_PATH = "TRAJECTORY_LOG_PATH"

_DB_URL = "postgresql://u:p@db.example.com:5432/orchestrator_analytics"

# Paths no read here ever opens; only which value comes back matters.
_PROBE_PATH = Path("/tmp/orchestrator-analytics-config-probe")


class LiveSettingsTest(unittest.TestCase):
    """`live_settings` reads off whichever settings holder the name resolves
    to, so patching a knob there is what the next read observes -- and a
    read's URL is the caller's argument whenever it passed one.
    """

    def test_the_holder_is_the_settings_owner(self) -> None:
        # Resolved here rather than bound at collection: the value of this
        # indirection is that it answers with whichever holder the name
        # resolves to when a read is actually made.
        self.assertIs(
            analytics_config.live_settings().holder,
            import_module("orchestrator.observability.analytics.settings"),
        )

    def test_omitted_url_falls_back_to_the_setting(self) -> None:
        holder = analytics_config.live_settings().holder
        with patch.object(holder, _ANALYTICS_DB_URL, _DB_URL):
            self.assertEqual(analytics_config.resolve_db_url(None), _DB_URL)

    def test_explicit_url_wins(self) -> None:
        holder = analytics_config.live_settings().holder
        override = "postgresql://override/db"
        with patch.object(holder, _ANALYTICS_DB_URL, _DB_URL):
            self.assertEqual(
                analytics_config.resolve_db_url(override), override,
            )


class CapturedHolderTest(unittest.TestCase):
    """`settings_on` answers for the holder a caller hands it, which is how a
    reader built against one import keeps resolving that import's values.
    """

    def test_a_patched_knob_reaches_the_next_read(self) -> None:
        # Read on demand rather than snapshotted at construction: the sink's
        # own tests patch a knob on the holder and expect a recorder already
        # holding a view of it to observe the new value.
        holder = analytics_config.live_settings().holder
        settings = analytics_config.settings_on(holder)
        with patch.object(holder, _TRAJECTORY_LOG_PATH, _PROBE_PATH):
            self.assertEqual(settings.trajectory_log_path, _PROBE_PATH)
        self.assertIsNone(settings.trajectory_log_path)

    def test_only_the_knob_asked_for_is_read(self) -> None:
        # Which is what lets a caller pass a holder carrying just the knobs it
        # touches, and what keeps a short-circuited condition from evaluating
        # the knob it never reached.
        settings = analytics_config.settings_on(
            SimpleNamespace(TRACK_SKILL_TRIGGERS=True),
        )
        self.assertTrue(settings.track_skill_triggers)
        self.assertRaises(AttributeError, attrgetter("log_path"), settings)


if __name__ == "__main__":
    unittest.main()
