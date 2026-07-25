# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Remote routing of the worktree new-commit probe."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from orchestrator import config, workflow, worktree_lifecycle

GIT_HELPER = "_git"
FAKE_WORKTREE = Path("/tmp/wt-not-real")
TEST_TARGET_ROOT = Path("/tmp/orchestrator-test-target-root")
DEFAULT_REVISION_RANGE = "origin/main..HEAD"


class _GitRecorder:
    def __init__(self, stdout: str = "") -> None:
        self.calls: list[tuple] = []
        self.stdout = stdout

    def __call__(self, *args, cwd):
        self.calls.append((args, cwd))
        return MagicMock(returncode=0, stdout=self.stdout, stderr="")


class HasNewCommitsRemoteNameTest(unittest.TestCase):
    """`_has_new_commits` must compare against `spec.remote_name`, not the
    hardcoded `origin`. With REPOS configured to drive a non-default remote
    (e.g. `private`), the rev-list base reference has to honor that or the
    handler will read stale commits from the wrong upstream."""

    def test_rev_list_references_per_spec_remote(self) -> None:
        git = _GitRecorder("0\n")
        private_spec = config.RepoSpec(
            slug="acme/widget",
            target_root=TEST_TARGET_ROOT,
            base_branch="main",
            remote_name="private",
        )
        with patch.object(worktree_lifecycle, GIT_HELPER, git):
            workflow._has_new_commits(private_spec, FAKE_WORKTREE)
        args, _cwd = git.calls[0]
        self.assertIn("private/main..HEAD", args)
        self.assertNotIn(DEFAULT_REVISION_RANGE, args)


if __name__ == "__main__":
    unittest.main()
