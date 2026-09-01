# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which file a read opens, and what an unconfigured sink answers with."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from orchestrator.observability.analytics import settings as analytics_settings
from orchestrator.observability.trajectory_viewer import constants, log_paths, reading
from tests.observability.trajectory_viewer.trajectory_viewer_test_support import (
    ISSUE,
    record,
)


_LOG_PATH_ATTR = "TRAJECTORY_LOG_PATH"

_CONFIGURED = Path("/var/log/traj.jsonl")

_EXPLICIT = Path("/var/log/asked-for.jsonl")


def _holder(log_path):
    """A settings holder carrying just the knob this owner reads."""
    return SimpleNamespace(TRAJECTORY_LOG_PATH=log_path)


class ConfiguredPathTest(unittest.TestCase):
    """The knob is read off the holder the caller hands in."""

    def test_each_holder_answers_with_its_own_knob(self) -> None:
        self.assertEqual(
            (
                log_paths.configured_path(_holder(_CONFIGURED)),
                log_paths.configured_path(_holder(None)),
            ),
            (_CONFIGURED, None),
        )

    def test_a_read_without_a_path_falls_back_to_it(self) -> None:
        self.assertEqual(
            log_paths.resolve_path(_holder(_CONFIGURED), None), _CONFIGURED,
        )

    def test_an_explicit_path_wins_over_it(self) -> None:
        # A caller pointing the reader at a file of its own is not asking
        # about the sink, so a disabled one costs it nothing.
        self.assertEqual(
            log_paths.resolve_path(_holder(None), _EXPLICIT), _EXPLICIT,
        )


class UnconfiguredMessageTest(unittest.TestCase):
    """An opt-in sink nobody switched on answers with the banner."""

    def test_a_disabled_sink_names_the_knob_to_set(self) -> None:
        self.assertEqual(
            log_paths.unconfigured_message(_holder(None)),
            constants.UNCONFIGURED_LOG_MESSAGE,
        )

    def test_a_configured_sink_has_nothing_to_say(self) -> None:
        self.assertIsNone(log_paths.unconfigured_message(_holder(_CONFIGURED)))


class SettingsHolderTest(unittest.TestCase):
    """The holder the page hands in is the analytics settings owner itself.

    Which is what makes a patch on that holder the interception every read the
    page makes goes through: the knob is read at call time off the holder that
    arrived rather than bound when the owner was imported.
    """

    def test_a_disabled_holder_reads_nothing(self) -> None:
        with patch.object(analytics_settings, _LOG_PATH_ATTR, None):
            configured = log_paths.configured_path(analytics_settings)
            self.assertEqual(reading.read_trajectories(configured), [])
            self.assertIsNone(configured)
            self.assertIsNotNone(
                log_paths.unconfigured_message(analytics_settings),
            )

    def test_a_configured_holder_names_the_file_read(self) -> None:
        with tempfile.TemporaryDirectory() as work_dir:
            path = Path(work_dir) / "traj.jsonl"
            written = json.dumps(record(issue=ISSUE))
            path.write_text(f"{written}\n", encoding="utf-8")
            with patch.object(analytics_settings, _LOG_PATH_ATTR, path):
                configured = log_paths.configured_path(analytics_settings)
                runs = reading.read_trajectories(configured)
                self.assertEqual(configured, path)
                self.assertIsNone(
                    log_paths.unconfigured_message(analytics_settings),
                )
        self.assertEqual([run.issue for run in runs], [ISSUE])


if __name__ == "__main__":
    unittest.main()
