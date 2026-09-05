# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The interval a terminal-artifact maintenance pass is owed at."""

import unittest

from tests.config import config_reload_helpers as _reload, config_test_values as _config_cases


class ArtifactCleanupIntervalConfigTest(unittest.TestCase):
    """How long a finished issue's worktrees and branches are left alone.

    A day by default, because what a pass reclaims is disk rather than
    anything the workflow waits on. A positive integer validated at import
    like the parallelism caps: zero or a negative interval would put a
    host-wide teardown between every pair of polling passes, each one holding
    scheduler admission closed while it proved the host quiet.
    """

    def test_default_is_one_day(self) -> None:
        config = _reload.load_config()
        self.assertEqual(
            config.TERMINAL_ARTIFACT_CLEANUP_INTERVAL_SECONDS,
            _config_cases._DEFAULT_CLEANUP_INTERVAL,
        )

    def test_env_override_wins(self) -> None:
        config = _reload.load_config(
            {
                _config_cases._CLEANUP_INTERVAL_ENV: str(
                    _config_cases._OVERRIDE_CLEANUP_INTERVAL,
                ),
            }
        )
        self.assertEqual(
            config.TERMINAL_ARTIFACT_CLEANUP_INTERVAL_SECONDS,
            _config_cases._OVERRIDE_CLEANUP_INTERVAL,
        )

    def test_blank_value_keeps_the_default(self) -> None:
        # An operator who commented the value out but left the key behind gets
        # the shipped cadence rather than an abort.
        config = _reload.load_config(
            {_config_cases._CLEANUP_INTERVAL_ENV: "  "},
        )
        self.assertEqual(
            config.TERMINAL_ARTIFACT_CLEANUP_INTERVAL_SECONDS,
            _config_cases._DEFAULT_CLEANUP_INTERVAL,
        )

    def test_an_invalid_interval_aborts_at_import(self) -> None:
        for spelling in ("nightly", _config_cases._DISABLED_ENV, "-1", "1.5"):
            with self.subTest(value=spelling):
                error_message = _reload.config_error_message(
                    {_config_cases._CLEANUP_INTERVAL_ENV: spelling},
                )
                self.assertIn(
                    _config_cases._CLEANUP_INTERVAL_ENV, error_message,
                )
                self.assertIn(spelling, error_message)


if __name__ == "__main__":
    unittest.main()
