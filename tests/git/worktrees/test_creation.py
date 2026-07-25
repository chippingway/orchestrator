# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Issue and PR worktree creation and the unpushed-work probe it gates on."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.git import commands
from orchestrator.git.worktrees import creation

from tests.git.worktrees.lifecycle_test_support import (
    BASE_BRANCH,
    ISSUE_BRANCH,
    LEGACY_BRANCH,
    ORIGIN_REMOTE,
    _GitRecorder,
    _git_result,
    _spec,
    _worktree_fixture,
)

FAKE_WORKTREE = Path("/tmp/wt-not-real")
PRIVATE_REMOTE = "private"
ADD_FAILURE_STDERR = "fatal: invalid reference"
CREATORS = (creation._ensure_worktree, creation._ensure_pr_worktree)


class EnsureWorktreeTest(unittest.TestCase):
    """A fresh implementing worktree starts from the base branch.

    A brand-new per-issue branch has no remote head to restore from, so a
    missing local ref is created off `<remote>/<base>`.
    """

    def test_existing_local_branch_is_checked_out(self) -> None:
        with _worktree_fixture() as fixture:
            worktree = fixture.run(creation._ensure_worktree)
            self.assertEqual(
                fixture.git.worktree_adds[0][2:],
                (str(worktree), ISSUE_BRANCH),
            )

    def test_missing_local_branch_starts_at_base(self) -> None:
        with _worktree_fixture(local_branch_present=False) as fixture:
            worktree = fixture.run(creation._ensure_worktree)
            self.assertEqual(
                fixture.git.worktree_adds[0][2:],
                (
                    "-b",
                    ISSUE_BRANCH,
                    str(worktree),
                    f"{ORIGIN_REMOTE}/{BASE_BRANCH}",
                ),
            )

    def test_pinned_branch_overrides_derivation(self) -> None:
        # An issue whose PR was opened before slug-namespacing keeps its
        # legacy ref in pinned state; forcing the derived name would orphan
        # that PR on a branch nothing pushes to.
        with _worktree_fixture(local_branch_present=False) as fixture:
            fixture.run(creation._ensure_worktree, branch=LEGACY_BRANCH)
            add_args = fixture.git.worktree_adds[0]
            self.assertIn(LEGACY_BRANCH, add_args)
            self.assertNotIn(ISSUE_BRANCH, add_args)

    def test_only_the_base_branch_is_fetched(self) -> None:
        with _worktree_fixture() as fixture:
            fixture.run(creation._ensure_worktree)
            self.assertEqual(fixture.fetches.branches, [BASE_BRANCH])
            self.assertEqual(fixture.git.plain_fetches, [])


class EnsurePrWorktreeTest(unittest.TestCase):
    """A PR worktree is restored from the PR's own remote head.

    `_ensure_worktree`'s base-branch fallback is right for a fresh run but
    wrong once a PR exists: rebuilding off `<remote>/<base>` would discard
    the dev's commits and leave the PR's conflicts unresolvable.
    """

    def test_missing_branch_restores_from_remote(self) -> None:
        with _worktree_fixture(local_branch_present=False) as fixture:
            worktree = fixture.run(creation._ensure_pr_worktree)
            self.assertEqual(
                fixture.git.worktree_adds[0][2:],
                (
                    "-b",
                    ISSUE_BRANCH,
                    str(worktree),
                    f"{ORIGIN_REMOTE}/{ISSUE_BRANCH}",
                ),
            )

    def test_existing_local_branch_is_checked_out(self) -> None:
        with _worktree_fixture() as fixture:
            worktree = fixture.run(creation._ensure_pr_worktree)
            add_args = fixture.git.worktree_adds[0]
            self.assertNotIn("-b", add_args)
            self.assertEqual(add_args[2:], (str(worktree), ISSUE_BRANCH))

    def test_base_and_branch_fetches_are_authed(self) -> None:
        with _worktree_fixture() as fixture:
            fixture.run(creation._ensure_pr_worktree)
            self.assertEqual(
                fixture.fetches.branches, [BASE_BRANCH, ISSUE_BRANCH],
            )
            self.assertEqual(fixture.git.plain_fetches, [])

    def test_every_git_call_runs_in_target_root(self) -> None:
        # The parent clone is operator-owned; running any of these in the
        # agent-writable worktree would resolve its `.git/config` instead.
        with _worktree_fixture() as fixture:
            fixture.run(creation._ensure_pr_worktree)
            for args, cwd in fixture.git.calls:
                self.assertEqual(cwd, fixture.spec.target_root, args)


class StaleWorktreeTest(unittest.TestCase):
    """What happens to a worktree an earlier tick left on disk.

    Reuse is what lets the orchestrator survive a crash between the agent
    committing and the push -- without it the next tick would wipe the work
    and burn another agent run on the same prompt. A worktree with nothing
    unpushed carries no such value and is force-removed so creation can
    start from a current base.
    """

    def test_unpushed_commits_are_reused_and_logged(self) -> None:
        for ensure in CREATORS:
            with (
                self.subTest(ensure=ensure.__name__),
                _worktree_fixture(
                    commit_probe=_git_result(stdout="2\n"),
                ) as fixture,
            ):
                planted = fixture.plant_issue_worktree()
                with self.assertLogs(creation.log, level="INFO") as logs:
                    worktree = fixture.run(ensure)
                    self.assertIn("reusing", "\n".join(logs.output))
                self.assertEqual(worktree, planted)
                self.assertEqual(fixture.git.worktree_adds, [])
                self.assertEqual(fixture.git.worktree_removes, [])

    def test_clean_worktree_is_force_removed(self) -> None:
        for ensure in CREATORS:
            with (
                self.subTest(ensure=ensure.__name__),
                _worktree_fixture() as fixture,
            ):
                planted = fixture.plant_issue_worktree()
                fixture.run(ensure)
                self.assertEqual(
                    fixture.git.worktree_removes[0][3:], (str(planted),),
                )
                self.assertTrue(fixture.git.worktree_adds)

    def test_failed_add_raises_with_git_error(self) -> None:
        # The caller has no worktree to hand the agent, so failing loudly
        # beats returning a path that is not a checkout.
        for ensure in CREATORS:
            with (
                self.subTest(ensure=ensure.__name__),
                _worktree_fixture(
                    worktree_add=_git_result(
                        returncode=1, stderr=ADD_FAILURE_STDERR,
                    ),
                ) as fixture,
                self.assertRaisesRegex(RuntimeError, ADD_FAILURE_STDERR),
            ):
                fixture.run(ensure)


class HasNewCommitsTest(unittest.TestCase):
    """The probe behind every reuse decision."""

    def test_rev_list_references_per_spec_remote(self) -> None:
        # With REPOS driving a non-default remote, a hardcoded `origin`
        # would read the wrong upstream and report stale commits.
        recorder = _GitRecorder()
        with patch.object(commands, "_git", recorder):
            creation._has_new_commits(_spec(PRIVATE_REMOTE), FAKE_WORKTREE)
        args, cwd = recorder.calls[0]
        self.assertIn(f"{PRIVATE_REMOTE}/{BASE_BRANCH}..HEAD", args)
        self.assertNotIn(f"{ORIGIN_REMOTE}/{BASE_BRANCH}..HEAD", args)
        self.assertEqual(cwd, FAKE_WORKTREE)

    def test_count_decides_the_verdict(self) -> None:
        # Empty output is what a worktree sitting exactly at base reports.
        for stdout, expected in (("3\n", True), ("0\n", False), ("", False)):
            recorder = _GitRecorder(commit_probe=_git_result(stdout=stdout))
            with (
                self.subTest(stdout=stdout),
                patch.object(commands, "_git", recorder),
            ):
                self.assertEqual(
                    creation._has_new_commits(_spec(), FAKE_WORKTREE),
                    expected,
                )

    def test_probe_failure_reports_no_commits(self) -> None:
        # A transient rev-list failure must not read as unpushed work, or
        # the creators would reuse a stale worktree indefinitely.
        recorder = _GitRecorder(commit_probe=_git_result(returncode=1))
        with patch.object(commands, "_git", recorder):
            self.assertFalse(
                creation._has_new_commits(_spec(), FAKE_WORKTREE),
            )


if __name__ == "__main__":
    unittest.main()
