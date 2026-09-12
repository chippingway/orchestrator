# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Bounded drain, group-liveness probe, and signal escalation owner tests."""

from __future__ import annotations

import contextlib
import signal
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from orchestrator.agents import process_groups as _process_groups
from tests.agents import agent_test_support as _support, agent_test_values as _agent_cases


class CommunicateBoundedTest(unittest.TestCase):
    """`communicate_bounded` is the shared drain primitive both the agent
    runner and the verify runner call. Its contract: return the captured
    streams (coercing an absent stream to ``""``) on completion, and ``None``
    when the drain itself blocks past the cap so the caller can escalate.
    """

    def test_returns_streams_coercing_absent_to_empty(self) -> None:
        proc = MagicMock()
        proc.communicate.return_value = (None, None)
        self.assertEqual(_process_groups.communicate_bounded(proc, 5), ("", ""))

    def test_returns_none_on_timeout(self) -> None:
        proc = MagicMock()
        proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd=_agent_cases._AGENT_COMMAND,
            timeout=5,
        )
        self.assertIsNone(_process_groups.communicate_bounded(proc, 5))


class ProcessGroupAliveTest(unittest.TestCase):
    """`process_group_alive` is the `killpg(_, 0)` probe both teardown paths
    read after their leader exits, so the mocked signal tests cannot exercise
    it. Driven against a real group: alive while the leader runs, empty once
    the group is killed and reaped.
    """

    def test_alive_until_group_killed_and_reaped(self) -> None:
        proc = subprocess.Popen(
            [sys.executable, _agent_cases._PYTHON_COMMAND_FLAG, "import time; time.sleep(120)"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with contextlib.ExitStack() as cleanup:
            cleanup.callback(_support.stop_process_group, proc)
            self.assertTrue(_process_groups.process_group_alive(proc.pid))
        self.assertFalse(_process_groups.process_group_alive(proc.pid))


class TerminateProcessGroupTest(unittest.TestCase):
    """`terminate_process_group` is the per-timeout cleanup. It must mirror
    `terminate_all_running`'s safety model: after the leader exits it probes
    the group with `killpg(_, 0)` and SIGKILLs any surviving descendant, so a
    build grandchild the agent forked cannot keep mutating the worktree after
    the timeout has already been recorded.
    """

    def test_sigkill_if_child_outlives_leader(self) -> None:
        # The leader exits on SIGTERM but a descendant in the same group
        # ignored it. `proc.wait()` returns, yet the signal-0 probe shows the
        # group still alive, so the group must be SIGKILLed.
        proc = MagicMock()
        proc.pid = 777
        proc.wait.return_value = 0  # leader exits promptly on SIGTERM

        with patch.object(
            _process_groups.os,
            _agent_cases._KILLPG,
            side_effect=_support.killpg_group_alive,
        ) as signal_mock:
            _process_groups.terminate_process_group(proc)
            sent = [call.args for call in signal_mock.call_args_list]
        self.assertIn((777, signal.SIGTERM), sent)
        self.assertIn((777, 0), sent)  # group liveness probed after leader exit
        self.assertIn((777, signal.SIGKILL), sent)

    def test_no_sigkill_when_group_fully_exited(self) -> None:
        # Leader exits and the signal-0 probe reports the group empty, so no
        # SIGKILL is sent -- the clean path.
        proc = MagicMock()
        proc.pid = 778
        proc.wait.return_value = 0

        with patch.object(
            _process_groups.os,
            _agent_cases._KILLPG,
            side_effect=_support.killpg_group_empty,
        ) as signal_mock:
            _process_groups.terminate_process_group(proc)
            sent = [call.args for call in signal_mock.call_args_list]
        self.assertIn((778, signal.SIGTERM), sent)
        self.assertIn((778, 0), sent)
        self.assertNotIn((778, signal.SIGKILL), sent)

    def test_sigkills_straggler_past_deadline(self) -> None:
        # The leader never exits on SIGTERM; once the grace `wait` times out
        # the group is SIGKILLed without a probe (a live leader means a live
        # group).
        proc = MagicMock()
        proc.pid = 779
        proc.wait.side_effect = subprocess.TimeoutExpired(
            cmd=_agent_cases._AGENT_COMMAND,
            timeout=5,
        )
        with patch.object(_process_groups.os, _agent_cases._KILLPG) as killpg:
            _process_groups.terminate_process_group(proc)
            calls = [call.args for call in killpg.call_args_list]
        self.assertIn((779, signal.SIGTERM), calls)
        self.assertIn((779, signal.SIGKILL), calls)
        self.assertNotIn((779, 0), calls)  # no probe when the leader is alive

    def test_first_sigterm_lookup_needs_no_kill(self) -> None:
        # The group already exited between the timeout firing and the killpg;
        # the ProcessLookupError race short-circuits before any wait/SIGKILL.
        proc = MagicMock()
        proc.pid = 780
        with patch.object(
            _process_groups.os,
            _agent_cases._KILLPG,
            side_effect=ProcessLookupError,
        ) as signal_mock:
            _process_groups.terminate_process_group(proc)
            sent = [call.args for call in signal_mock.call_args_list]
        self.assertEqual(
            sent,
            [(780, signal.SIGTERM)],
        )
        proc.wait.assert_not_called()
