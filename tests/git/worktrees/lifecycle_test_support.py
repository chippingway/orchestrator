# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Faked git plumbing and a temp worktrees root for the lifecycle owners."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional
from unittest.mock import MagicMock, patch

from orchestrator import config
from orchestrator.git import authentication, commands
from orchestrator.git.worktrees import decomposition, paths

BASE_BRANCH = "main"
ORIGIN_REMOTE = "origin"
PRIVATE_REMOTE = "private"
REPO_SLUG = "acme/widget"
TARGET_ROOT = Path("/tmp/orchestrator-test-target-root")
ISSUE_NUMBER = 300
ISSUE_BRANCH = "orchestrator/acme__widget/issue-300"
LEGACY_BRANCH = "orchestrator/issue-300"
FETCH = "fetch"
REV_LIST = "rev-list"
REV_PARSE = "rev-parse"
WORKTREE_ADD = ("worktree", "add")
WORKTREE_REMOVE_FORCE = ("worktree", "remove", "--force")

_GitArgs = tuple[str, ...]
_GitCall = tuple[_GitArgs, Path]


def _git_result(
    *, returncode: int = 0, stdout: str = "", stderr: str = "",
) -> MagicMock:
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


def _spec(remote_name: str = ORIGIN_REMOTE) -> config.RepoSpec:
    return config.RepoSpec(
        slug=REPO_SLUG,
        target_root=TARGET_ROOT,
        base_branch=BASE_BRANCH,
        remote_name=remote_name,
    )


class _GitRecorder:
    """Answer the probes the lifecycle owners make and record every call.

    `local_branch_present` drives the `rev-parse --verify <branch>` probe
    that decides between attaching to an existing ref and restoring one;
    `commit_probe` and `worktree_add` let a test hand back the exact
    `rev-list --count` and `worktree add` results a scenario needs.
    """

    def __init__(
        self,
        *,
        local_branch_present: bool = True,
        commit_probe: Optional[MagicMock] = None,
        worktree_add: Optional[MagicMock] = None,
    ) -> None:
        self.calls: list[_GitCall] = []
        self.local_branch_present = local_branch_present
        self.commit_probe = commit_probe or _git_result()
        self.worktree_add = worktree_add or _git_result()

    def __call__(self, *args: str, cwd: Path) -> MagicMock:
        self.calls.append((args, cwd))
        if args[0] == REV_PARSE:
            return _git_result(returncode=0 if self.local_branch_present else 1)
        if args[0] == REV_LIST:
            return self.commit_probe
        if args[:2] == WORKTREE_ADD:
            return self.worktree_add
        return _git_result()

    @property
    def worktree_adds(self) -> list[_GitArgs]:
        return [args for args, _cwd in self.calls if args[:2] == WORKTREE_ADD]

    @property
    def worktree_removes(self) -> list[_GitArgs]:
        return [
            args
            for args, _cwd in self.calls
            if args[:3] == WORKTREE_REMOVE_FORCE
        ]

    @property
    def plain_fetches(self) -> list[_GitArgs]:
        """Fetches that bypassed the authenticated helper.

        A plain `git fetch` inherits the ambient credential helper, which
        under systemd has none -- every fetch has to ride the askpass token.
        """
        return [args for args, _cwd in self.calls if args[0] == FETCH]


class _AuthedFetchRecorder:
    """Record the branches handed to the authenticated target-root fetch."""

    def __init__(self) -> None:
        self.branches: list[str] = []

    def __call__(self, _spec_arg: config.RepoSpec, branch: str) -> MagicMock:
        self.branches.append(branch)
        return _git_result()


@dataclass(frozen=True)
class _WorktreeFixture:
    """Recorders plus the temp worktrees root one patched run observes."""

    git: _GitRecorder
    fetches: _AuthedFetchRecorder
    spec: config.RepoSpec

    def plant_issue_worktree(self) -> Path:
        """Leave a per-issue worktree on disk for the creators to find."""
        worktree = paths._worktree_path(self.spec, ISSUE_NUMBER)
        worktree.mkdir(parents=True)
        return worktree

    def plant_decompose_worktree(self) -> Path:
        """Leave a decomposer scratch checkout on disk from a prior run."""
        worktree = decomposition._decompose_worktree_path(
            self.spec, ISSUE_NUMBER,
        )
        worktree.mkdir(parents=True)
        return worktree

    def run(self, ensure, **options) -> Path:
        return ensure(self.spec, ISSUE_NUMBER, **options)


@contextmanager
def _worktree_fixture(**recorder_options) -> Iterator[_WorktreeFixture]:
    """Point the worktrees root at a temp dir and fake the git plumbing.

    The owners bind `git.commands` and `git.authentication` directly, so a
    test that has to intercept what they run patches those owners.
    `WORKTREES_DIR` moves so `Path.exists()` answers for
    real -- the reuse decision turns on it.
    """
    recorder = _GitRecorder(**recorder_options)
    fetches = _AuthedFetchRecorder()
    with tempfile.TemporaryDirectory(prefix="orch-worktree-") as temp_dir:
        with (
            patch.object(config, "WORKTREES_DIR", Path(temp_dir)),
            patch.object(commands, "_git", recorder),
            patch.object(authentication, "_authed_target_fetch", fetches),
        ):
            yield _WorktreeFixture(
                git=recorder, fetches=fetches, spec=_spec(),
            )
