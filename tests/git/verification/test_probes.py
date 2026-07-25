# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""HEAD and dirty-file probing owned by the verification probe module."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.git import commands
from orchestrator.git.verification import probes

from tests.workflow_helpers import TEST_BASE_BRANCH

GIT_COMMAND = "git"
QUIET_FLAG = "-q"
GIT_CONFIG = "config"
SEED_FILE = "seed"
LEFTOVER_FILE = "leftover.txt"
EXECUTABLE_MODE = 0o755
HEAD_SHA = "f00dcafe"
GIT_FAILURE = 128
WORKTREE = Path("/tmp/orchestrator-test-verification-probes")

# Porcelain v1 status lines and the paths they name.
PORCELAIN_CASES = (
    (" M src/app.py", ["src/app.py"]),
    ("?? leftover.txt", ["leftover.txt"]),
    ("R  old.py -> new.py", ["new.py"]),
    ('?? "quoted path.txt"', ["quoted path.txt"]),
    ("??", []),
    (" M  ", []),
)


def _completed(returncode: int, stdout: str) -> subprocess.CompletedProcess:
    """Return a git result carrying the given exit status and stdout."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout)


def _run_git(*args: str, cwd: Path) -> None:
    subprocess.run(
        [GIT_COMMAND, *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


class HeadShaProbeTest(unittest.TestCase):
    """`_head_sha` snapshots HEAD so a verify-time commit can be detected."""

    def test_reports_the_trimmed_rev_parse_output(self) -> None:
        with patch.object(commands, "_git", return_value=_completed(0, f"{HEAD_SHA}\n")) as git:
            self.assertEqual(probes._head_sha(WORKTREE), HEAD_SHA)
            self.assertEqual(git.call_args.args, ("rev-parse", "HEAD"))
            self.assertEqual(git.call_args.kwargs["cwd"], WORKTREE)

    def test_unreadable_head_reports_no_snapshot(self) -> None:
        # An uninitialized repo has no HEAD to read. The runner treats the
        # empty baseline as "no HEAD ever existed" and accepts only an
        # unchanged "" afterwards, so the probe must not invent a SHA.
        with patch.object(commands, "_git", return_value=_completed(GIT_FAILURE, "fatal: bad revision")):
            self.assertEqual(probes._head_sha(WORKTREE), "")


class PorcelainParsingTest(unittest.TestCase):
    """`_worktree_dirty_files` turns porcelain v1 lines into paths."""

    def test_each_status_line_yields_its_path(self) -> None:
        for line, expected in PORCELAIN_CASES:
            with self.subTest(line=line):
                with patch.object(commands, "_git_hardened", return_value=_completed(0, line)):
                    self.assertEqual(probes._worktree_dirty_files(WORKTREE), expected)

    def test_all_reported_paths_are_collected(self) -> None:
        status = "\n".join(line for line, paths in PORCELAIN_CASES if paths)
        with patch.object(commands, "_git_hardened", return_value=_completed(0, status)):
            self.assertEqual(
                probes._worktree_dirty_files(WORKTREE),
                ["src/app.py", LEFTOVER_FILE, "new.py", "quoted path.txt"],
            )

    def test_failed_probe_reports_a_clean_tree(self) -> None:
        # A probe that could not run proves nothing about the tree, and the
        # callers that refuse to publish on dirtiness read the list directly.
        with patch.object(commands, "_git_hardened", return_value=_completed(GIT_FAILURE, LEFTOVER_FILE)):
            self.assertEqual(probes._worktree_dirty_files(WORKTREE), [])


class WorktreeDirtyFilesHardeningTest(unittest.TestCase):
    """`_worktree_dirty_files` runs its `git status` probe through the
    hardened git path, so an agent-planted `core.fsmonitor` in the worktree
    config cannot execute with the orchestrator's process environment. Every
    caller passes an agent-writable worktree, so the probe is hardened
    unconditionally. Real modifications are still reported; only fsmonitor
    execution and the global-config trust boundary are dropped.
    """

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="orch-dirty-hardening-"))
        self.addCleanup(shutil.rmtree, str(self.tmpdir), ignore_errors=True)
        self.work = self.tmpdir / "work"
        self.work.mkdir()
        _run_git("init", QUIET_FLAG, "-b", TEST_BASE_BRANCH, cwd=self.work)
        _run_git(GIT_CONFIG, "user.email", "t@t", cwd=self.work)
        _run_git(GIT_CONFIG, "user.name", "t", cwd=self.work)
        (self.work / SEED_FILE).write_text("x\n")
        _run_git("add", ".", cwd=self.work)
        _run_git("commit", QUIET_FLAG, "-m", SEED_FILE, cwd=self.work)

    def test_blocks_planted_fsmonitor_reports_dirty(self) -> None:
        # Hook + marker live outside the worktree so they are not themselves
        # untracked files. The `/`+NUL response is fsmonitor v1 for "assume
        # everything changed" -- a scan hint only, so a clean tree reads clean.
        marker = self.tmpdir / "fsmonitor_ran.txt"
        hook = self.tmpdir / "fsmonitor_hook.sh"
        hook.write_text(
            f"#!/bin/sh\nprintf ran >> '{marker}'\nprintf '/\\000'\n"
        )
        hook.chmod(EXECUTABLE_MODE)
        _run_git(GIT_CONFIG, "core.fsmonitor", str(hook), cwd=self.work)

        (self.work / LEFTOVER_FILE).write_text("leak\n")
        # Prove the planted hook is genuinely honored: a plain, unhardened
        # index refresh fires it. Without this the empty-marker assertion
        # below could pass simply because the hook was never wired.
        _run_git("status", "--porcelain", cwd=self.work)
        self.assertTrue(
            marker.exists() and marker.read_text(),
            "planted fsmonitor never fired for a plain git status; the test cannot detect a regression",
        )
        marker.unlink()

        dirty = probes._worktree_dirty_files(self.work)

        # The real modification is still reported...
        self.assertIn(LEFTOVER_FILE, dirty)
        # ...but the hardened probe never executed the planted helper with
        # our process environment attached.
        self.assertFalse(
            marker.exists() and marker.read_text(),
            "hardened dirty probe executed the planted core.fsmonitor",
        )


if __name__ == "__main__":
    unittest.main()
