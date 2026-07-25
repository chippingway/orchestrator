# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A real bare remote and worker drivers for the creation smoke test."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from orchestrator import config
from orchestrator.git import authentication, locks
from orchestrator.git.worktrees import creation

from tests.git.concurrency_test_support import _start_and_join

GIT_COMMAND = "git"
BASE_BRANCH = "main"
ORIGIN_REMOTE = "origin"
REAL_GIT_TIMEOUT_SECONDS = 30.0


def _run_git(
    *args: str,
    cwd: Path,
    env_extra: dict | None = None,
) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    if env_extra:
        env.update(env_extra)
    git_result = subprocess.run(
        [GIT_COMMAND, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return git_result.stdout


def _local_fetch(spec, branch):
    """Stand in for the token-bearing fetch against a file:// remote."""
    return subprocess.run(
        [GIT_COMMAND, "fetch", "--quiet", spec.remote_name, branch],
        cwd=str(spec.target_root),
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


class _RealGitWorktreeRepo:
    """A seeded clone of a real bare remote for the creators to work in."""

    def __init__(self) -> None:
        self._tmpdir = Path(tempfile.mkdtemp(prefix="orch-ensure-real-"))
        self._remote = self._tmpdir / "remote.git"
        self._work = self._tmpdir / "work"
        self.spec = config.RepoSpec(
            slug="acme/widget",
            target_root=self._work,
            base_branch=BASE_BRANCH,
            remote_name=ORIGIN_REMOTE,
        )

    def prepare(self, test_case) -> None:
        locks._TARGET_ROOT_LOCKS.clear()
        test_case.addCleanup(shutil.rmtree, str(self._tmpdir), ignore_errors=True)
        self._initialize_remote()
        self._seed_initial_commit()
        self._patch_runtime(test_case)

    def _initialize_remote(self) -> None:
        subprocess.run(
            [GIT_COMMAND, "init", "--bare", "-b", BASE_BRANCH, str(self._remote)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [GIT_COMMAND, "clone", str(self._remote), str(self._work)],
            check=True,
            capture_output=True,
        )

    def _seed_initial_commit(self) -> None:
        author_env = {
            "GIT_AUTHOR_NAME": "Dev",
            "GIT_AUTHOR_EMAIL": "dev@example.com",
            "GIT_COMMITTER_NAME": "Dev",
            "GIT_COMMITTER_EMAIL": "dev@example.com",
        }
        (self._work / "README.md").write_text("hello\n")
        _run_git("add", ".", cwd=self._work)
        _run_git(
            "commit",
            "-m",
            "initial",
            cwd=self._work,
            env_extra=author_env,
        )
        _run_git("push", ORIGIN_REMOTE, BASE_BRANCH, cwd=self._work)

    def _patch_runtime(self, test_case) -> None:
        worktrees_patch = patch.object(
            config,
            "WORKTREES_DIR",
            self._tmpdir / "worktrees",
        )
        fetch_patch = patch.object(
            authentication,
            "_authed_target_fetch",
            side_effect=_local_fetch,
        )
        worktrees_patch.start()
        fetch_patch.start()
        test_case.addCleanup(worktrees_patch.stop)
        test_case.addCleanup(fetch_patch.stop)


class _EnsureRecorder:
    """Run `_ensure_worktree` per worker and keep each thread's outcome."""

    def __init__(self, spec: config.RepoSpec) -> None:
        self.outcomes: list[tuple[int, Path | None, BaseException | None]] = []
        self._spec = spec
        self._lock = threading.Lock()

    def __call__(self, issue_number: int) -> None:
        try:
            outcome = (
                issue_number,
                creation._ensure_worktree(self._spec, issue_number),
                None,
            )
        except BaseException as error:  # noqa: BLE001 - asserted by the test
            outcome = (issue_number, None, error)
        with self._lock:
            self.outcomes.append(outcome)

    def run_workers(self, test_case, issue_numbers) -> None:
        threads = [
            threading.Thread(target=self, args=(issue_number,))
            for issue_number in issue_numbers
        ]
        _start_and_join(threads, timeout=REAL_GIT_TIMEOUT_SECONDS)
        for thread in threads:
            test_case.assertFalse(
                thread.is_alive(),
                "worker timed out (possible lock contention)",
            )

    def assert_all_succeeded(self, test_case, issue_numbers) -> None:
        errors = [
            (issue_number, error)
            for issue_number, _worktree, error in self.outcomes
            if error is not None
        ]
        test_case.assertEqual(errors, [])
        test_case.assertEqual(
            tuple(sorted(number for number, _, _ in self.outcomes)),
            issue_numbers,
        )

    def assert_worktrees_exist(self, test_case) -> None:
        for issue_number, worktree, _error in self.outcomes:
            test_case.assertTrue(
                worktree is not None and worktree.exists(),
                f"worktree {worktree} missing for issue #{issue_number}",
            )
