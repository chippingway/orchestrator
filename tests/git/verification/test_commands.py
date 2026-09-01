# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Sequencing and captured output of a real `VERIFY_COMMANDS` run."""

from __future__ import annotations

import shlex
import unittest

from orchestrator.git.verification import runner
from tests.git.verification import command_helpers

VERIFY_FAILED = "failed"
VERIFY_OK = "ok"
OUTPUT_PAYLOAD_SIZE = 10000
OUTPUT_BUDGET = 4096
PASSING_COMMAND = "true"


class RunVerifyCommandsTest(
    command_helpers.VerifyCommandsFixtureMixin,
    unittest.TestCase,
):
    """Run each command in order and report the first non-zero exit."""

    def test_empty_commands_short_circuits_to_ok(self) -> None:
        run = runner._run_verify_commands(self.worktree, (), 60)
        self.assertEqual(run.status, VERIFY_OK)
        self.assertIsNone(run.command)

    def test_all_commands_pass_returns_ok(self) -> None:
        run = runner._run_verify_commands(
            self.worktree,
            (PASSING_COMMAND, "echo hello"),
            60,
        )
        self.assertEqual(run.status, VERIFY_OK)

    def test_nonzero_names_first_failed_command(self) -> None:
        run = runner._run_verify_commands(
            self.worktree,
            (PASSING_COMMAND, "sh -c 'echo boom 1>&2; exit 3'", PASSING_COMMAND),
            60,
        )
        self.assertEqual(run.status, VERIFY_FAILED)
        self.assertEqual(run.command, "sh -c 'echo boom 1>&2; exit 3'")
        self.assertEqual(run.exit_code, 3)
        self.assertIn("boom", run.output)

    def test_output_truncated_to_budget(self) -> None:
        padding = "X" * OUTPUT_PAYLOAD_SIZE
        big = f"{padding}TAIL"
        run = runner._run_verify_commands(
            self.worktree,
            (f"sh -c 'printf %s {shlex.quote(big)}; exit 1'",),
            60,
        )
        self.assertEqual(run.status, VERIFY_FAILED)
        # Tail preserved, leading bulk trimmed.
        self.assertIn("TAIL", run.output)
        self.assertLessEqual(len(run.output), OUTPUT_BUDGET)


if __name__ == "__main__":
    unittest.main()
