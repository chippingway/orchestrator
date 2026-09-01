# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Decomposer worktree path, fresh creation, and best-effort removal."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git import commands
from orchestrator.git.worktrees import decomposition, paths
from tests.git.worktrees.lifecycle_test_support import (
    BASE_BRANCH,
    ORIGIN_REMOTE,
    _git_result,
    _worktree_fixture,
)
from tests.git.worktrees.path_test_support import (
    ALICE_REPO_SLUG,
    BOB_REPO_SLUG,
    STAGE_LAYOUT_ISSUE_NUMBER,
    _spec,
)

ADD_FAILURE_STDERR = "fatal: invalid reference"
DETACH_FLAG = "--detach"
COLLIDING_ISSUE_NUMBER = 7


class DecomposeWorktreePathTest(unittest.TestCase):
    """Where the decomposer's scratch checkout lands on disk."""

    def test_distinct_slugs_never_collide(self) -> None:
        self.assertNotEqual(
            decomposition._decompose_worktree_path(
                _spec(ALICE_REPO_SLUG), COLLIDING_ISSUE_NUMBER,
            ),
            decomposition._decompose_worktree_path(
                _spec(BOB_REPO_SLUG), COLLIDING_ISSUE_NUMBER,
            ),
        )

    def test_stages_share_the_repo_namespace(self) -> None:
        # `<slug>/issue-N` and `<slug>/decompose-N` share the per-repo
        # subdirectory so reaping the parent also reaps the scratch.
        spec = _spec("owner/name")
        self.assertEqual(
            paths._worktree_path(spec, STAGE_LAYOUT_ISSUE_NUMBER).parent,
            decomposition._decompose_worktree_path(
                spec, STAGE_LAYOUT_ISSUE_NUMBER,
            ).parent,
        )


class EnsureDecomposeWorktreeTest(unittest.TestCase):
    """The decomposer is read-only and stateless across runs, so its
    checkout is rebuilt detached at the current base every time rather
    than reused like the per-issue worktrees.
    """

    def test_detached_checkout_anchors_on_base(self) -> None:
        with _worktree_fixture() as fixture:
            worktree = fixture.run(decomposition._ensure_decompose_worktree)
            self.assertEqual(
                fixture.git.worktree_adds[0][2:],
                (
                    DETACH_FLAG,
                    str(worktree),
                    f"{ORIGIN_REMOTE}/{BASE_BRANCH}",
                ),
            )
            self.assertEqual(fixture.fetches.branches, [BASE_BRANCH])
            self.assertEqual(fixture.git.plain_fetches, [])

    def test_leftover_scratch_is_force_removed(self) -> None:
        with _worktree_fixture() as fixture:
            planted = fixture.plant_decompose_worktree()
            fixture.run(decomposition._ensure_decompose_worktree)
            self.assertEqual(
                fixture.git.worktree_removes[0][3:], (str(planted),),
            )
            self.assertTrue(fixture.git.worktree_adds)

    def test_failed_add_raises_with_git_error(self) -> None:
        with (
            _worktree_fixture(
                worktree_add=_git_result(
                    returncode=1, stderr=ADD_FAILURE_STDERR,
                ),
            ) as fixture,
            self.assertRaisesRegex(RuntimeError, ADD_FAILURE_STDERR),
        ):
            fixture.run(decomposition._ensure_decompose_worktree)


class DecomposeWorktreeRemovalTest(unittest.TestCase):
    """`_cleanup_decompose_worktree` runs from `_handle_decomposing`'s
    `finally`, so it must never raise -- a cleanup failure would mask the
    handler's original error. Every step, including resolving the worktree
    path, rides the best-effort guard.
    """

    def test_absent_scratch_skips_the_removal(self) -> None:
        with _worktree_fixture() as fixture:
            fixture.run(decomposition._run_decompose_worktree_removal)
            self.assertEqual(fixture.git.calls, [])

    def test_present_scratch_is_force_removed(self) -> None:
        with _worktree_fixture() as fixture:
            planted = fixture.plant_decompose_worktree()
            fixture.run(decomposition._cleanup_decompose_worktree)
            self.assertEqual(
                fixture.git.worktree_removes[0][3:], (str(planted),),
            )

    def test_swallows_path_resolution_failure(self) -> None:
        with (
            _worktree_fixture() as fixture,
            patch.object(
                paths,
                "_repo_worktrees_root",
                side_effect=RuntimeError("bad spec"),
            ),
            self.assertLogs(decomposition.log, level="ERROR"),
        ):
            fixture.run(decomposition._cleanup_decompose_worktree)

    def test_swallows_git_removal_failure(self) -> None:
        with _worktree_fixture() as fixture:
            fixture.plant_decompose_worktree()
            with (
                patch.object(
                    commands, "_git", side_effect=OSError("git not found"),
                ),
                self.assertLogs(decomposition.log, level="ERROR"),
            ):
                fixture.run(decomposition._cleanup_decompose_worktree)


if __name__ == "__main__":
    unittest.main()
