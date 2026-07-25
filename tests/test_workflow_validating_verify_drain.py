# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import subprocess
import unittest
from unittest.mock import MagicMock

from orchestrator import verify


class DrainVerifyOutputTest(unittest.TestCase):
    """`_drain_verify_output` reads a killed verify shell's buffered output.
    The first bounded drain covers the normal case; if it wedges -- a
    descendant that escaped the group is still holding the pipe fd open -- it
    escalates to `proc.kill()` and one more bounded drain, then gives up with
    empty output. Popen is faked so the wedged path is deterministic.
    """

    def test_first_drain_returns_without_extra_kill(self) -> None:
        proc = MagicMock()
        proc.communicate.return_value = ("out", "err")
        self.assertEqual(verify._drain_verify_output(proc), ("out", "err"))
        proc.kill.assert_not_called()

    def test_wedged_drain_kills_then_returns_output(self) -> None:
        proc = MagicMock()
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="verify", timeout=5),
            ("late-out", "late-err"),
        ]
        self.assertEqual(
            verify._drain_verify_output(proc),
            ("late-out", "late-err"),
        )
        proc.kill.assert_called_once()

    def test_both_drains_time_out_returns_empty(self) -> None:
        proc = MagicMock()
        proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="verify",
            timeout=5,
        )
        self.assertEqual(verify._drain_verify_output(proc), ("", ""))
        proc.kill.assert_called_once()
