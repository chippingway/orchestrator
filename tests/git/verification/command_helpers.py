# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Fixtures for running real verify commands against a real git worktree.

The dirty and HEAD probes read git state, so the classification paths can
only be exercised against a repository with a commit in it.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from orchestrator.agents import processes

from tests.workflow_helpers import TEST_BASE_BRANCH

GIT_COMMAND = "git"
QUIET_FLAG = "-q"
WORKTREE_FLAG = "-C"
GIT_CONFIG = "config"
SEED_FILE = "seed"


class RegisteredCommunicate:
    def __init__(self, process, seen):
        self.process = process
        self.seen = seen

    def __call__(self, *_args, **_kwargs):
        with processes._running_procs_lock:
            self.seen["during"] = self.process in processes._running_procs
        return "", ""


class VerifyCommandsFixtureMixin:
    def setUp(self) -> None:
        self.worktree = Path(tempfile.mkdtemp())
        worktree = str(self.worktree)
        # Initialize a git repo so the dirty-detection branch works.
        subprocess.run(
            [GIT_COMMAND, "init", QUIET_FLAG, "-b", TEST_BASE_BRANCH, worktree],
            check=True,
        )
        subprocess.run(
            [GIT_COMMAND, WORKTREE_FLAG, worktree, GIT_CONFIG, "user.email", "t@t"],
            check=True,
        )
        subprocess.run(
            [GIT_COMMAND, WORKTREE_FLAG, worktree, GIT_CONFIG, "user.name", "t"],
            check=True,
        )
        (self.worktree / SEED_FILE).write_text("x")
        subprocess.run(
            [GIT_COMMAND, WORKTREE_FLAG, worktree, "add", "."],
            check=True,
        )
        subprocess.run(
            [GIT_COMMAND, WORKTREE_FLAG, worktree, "commit", QUIET_FLAG, "-m", SEED_FILE],
            check=True,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.worktree, ignore_errors=True)
