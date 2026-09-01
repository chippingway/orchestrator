# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A real repository left mid-rebase for the crash-recovery owners to finish.

The recovery reads its facts through hardened git argv -- a fetch refspec, a
`rev-parse` of a remote-tracking ref, an ahead/behind count, a porcelain dirty
scan -- and a subprocess double would let a wrong ref or a wrong refspec pass
unnoticed. These fixtures therefore build an actual bare remote and clone and
stub only the two network hops, so the branch state each scenario asserts on
is the one git itself computed.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from types import MappingProxyType
from unittest import mock

from orchestrator import config
from orchestrator.git import authentication
from orchestrator.git.base_sync import recovery

from tests.git.base_sync.gate_reads_support import _gate_base_reads
from tests.support.fakes import (
    FakeGitHubClient,
    FakePR,
    FakePRRef,
    make_issue,
)

ISSUE = 7

PR_NUMBER = 42

SLUG = "acme/widget"

BASE_BRANCH = "main"

BRANCH = "orchestrator/acme__widget/issue-7"

REMOTE_NAME = "origin"

LABEL = "in_review"

VALIDATING = "workflow:validating"

GIT = "git"

PUSH = "push"

REV_PARSE = "rev-parse"

HEAD_REF = "HEAD"

BRANCH_REF = f"refs/heads/{BRANCH}"

AUTHED_FETCH = "_authed_fetch"

PUSH_BRANCH = "_push_branch"

FEATURE_FILE = "feature.py"

SCRATCH_FILE = "scratch.txt"

PARK_PUSH_FAILED = "auto_base_rebase_push_failed"

PARK_DIRTY = "auto_base_rebase_dirty"

KEY_AWAITING_HUMAN = "awaiting_human"

KEY_PARK_REASON = "park_reason"

KEY_PENDING_PUSH_SHA = "pending_auto_base_rebase_push_sha"

EVENT_FIELD = "event"

METHOD_FIELD = "method"

REBASED_EVENT = "base_rebased"

_AUTHOR_ENV = MappingProxyType(
    {
        "GIT_AUTHOR_NAME": "Dev",
        "GIT_AUTHOR_EMAIL": "dev@example.com",
        "GIT_COMMITTER_NAME": "Dev",
        "GIT_COMMITTER_EMAIL": "dev@example.com",
    },
)


def run_git(*args: str, cwd: Path, authored: bool = False) -> str:
    """Run one real `git` command in `cwd` and return its stdout."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    if authored:
        env.update(_AUTHOR_ENV)
    completed = subprocess.run(
        [GIT, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return completed.stdout


def commit(worktree: Path, filename: str, body: str, message: str) -> str:
    """Commit `body` into `filename` and return the resulting HEAD SHA."""
    (worktree / filename).write_text(body)
    run_git("add", ".", cwd=worktree)
    run_git("commit", "-m", message, cwd=worktree, authored=True)
    return head_sha(worktree)


def head_sha(cwd: Path, ref: str = HEAD_REF) -> str:
    """Resolve `ref` in `cwd` -- a worktree or the bare remote itself."""
    return run_git(REV_PARSE, ref, cwd=cwd).strip()


def _local_fetch(_spec, refspec: str, *, cwd: Path):
    """Stand in for the authenticated fetch against the local bare remote."""
    return subprocess.run(
        [GIT, "fetch", "--quiet", REMOTE_NAME, refspec],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        check=False,
    )


class _LocalLeasePush:
    """Run the leased force-push the recovery reissues against the remote."""

    def __init__(self) -> None:
        self.leases: list[str] = []

    def __call__(
        self, _spec, worktree, branch, *,
        force_with_lease=None, revision=None,
    ):
        self.leases.append(force_with_lease or "")
        source = revision or HEAD_REF
        pushed = subprocess.run(
            [
                GIT,
                PUSH,
                f"--force-with-lease=refs/heads/{branch}:{force_with_lease}",
                REMOTE_NAME,
                f"{source}:refs/heads/{branch}",
            ],
            cwd=str(worktree),
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            check=False,
        )
        return pushed.returncode == 0


class _RecoveryRepositoryBuilder:
    """Seed the remote, the clone, and the head an interrupted rebase left."""

    def __init__(self, fixture) -> None:
        self._fixture = fixture

    def prepare(self) -> None:
        self._init_remote()
        self._seed_branch()
        self._rewrite_head()
        self._seed_issue()

    def _init_remote(self) -> None:
        fixture = self._fixture
        fixture.remote = fixture.tmpdir / "remote.git"
        subprocess.run(
            [GIT, "init", "--bare", "-b", BASE_BRANCH, str(fixture.remote)],
            check=True,
            capture_output=True,
        )
        fixture.work = fixture.tmpdir / "work"
        subprocess.run(
            [GIT, "clone", str(fixture.remote), str(fixture.work)],
            check=True,
            capture_output=True,
        )

    def _seed_branch(self) -> None:
        fixture = self._fixture
        commit(fixture.work, "README.md", "hello\n", "initial")
        run_git(PUSH, REMOTE_NAME, BASE_BRANCH, cwd=fixture.work)
        run_git("checkout", "-b", BRANCH, cwd=fixture.work)
        fixture.anchor = commit(
            fixture.work, FEATURE_FILE, "feature\n", "feat: add feature",
        )
        run_git(PUSH, REMOTE_NAME, BRANCH, cwd=fixture.work)

    def _rewrite_head(self) -> None:
        """Leave HEAD where an interrupted rebase would have left it."""
        fixture = self._fixture
        fixture.recovered = commit(
            fixture.work,
            FEATURE_FILE,
            "feature rebased\n",
            "feat: rebased onto the advanced base",
        )

    def _seed_issue(self) -> None:
        fixture = self._fixture
        fixture.spec = config.RepoSpec(
            slug=SLUG,
            target_root=fixture.work,
            base_branch=BASE_BRANCH,
        )
        fixture.gh = FakeGitHubClient()
        fixture.issue = make_issue(ISSUE, label=LABEL)
        fixture.gh.add_issue(fixture.issue)
        fixture.gh.seed_state(
            ISSUE,
            pr_number=PR_NUMBER,
            branch=BRANCH,
            pending_auto_base_rebase_push_sha=fixture.anchor,
        )
        # Standing on the head this recovery leases its push against, which
        # is the commit the interrupted rebase left the remote on: the size
        # gate compares the two readings of that one fact and refuses a call
        # whose publication moved out from under it.
        fixture.gh.add_pr(FakePR(
            number=PR_NUMBER,
            head_branch=BRANCH,
            head=FakePRRef(sha=fixture.anchor),
        ))
        # The recovered head is measured before it is pushed, and this
        # fixture has no token to read a remote base with -- the reading gets
        # its ordinary answers so the test stays about the git side of the
        # recovery.
        _gate_base_reads(fixture)


class RecoveryGitFixtureMixin:
    """An issue whose rebase finished locally but never reached the remote."""

    def setUp(self) -> None:
        self.tmpdir = Path(
            self.enterContext(
                tempfile.TemporaryDirectory(
                    prefix="orch-base-sync-recovery-",
                    ignore_cleanup_errors=True,
                ),
            ),
        )
        _RecoveryRepositoryBuilder(self).prepare()
        self.push = _LocalLeasePush()
        self.enterContext(
            mock.patch.object(authentication, AUTHED_FETCH, _local_fetch),
        )
        self.enterContext(
            mock.patch.object(authentication, PUSH_BRANCH, self.push),
        )

    def recover(self) -> bool:
        """Run the recovery the way the refresh flow enters it."""
        return recovery._recover_pending_auto_base_rebase(
            self.gh,
            self.spec,
            self.issue,
            self.gh.read_pinned_state(self.issue),
            self.work,
            pr_number=PR_NUMBER,
            label=LABEL,
            pending_pre_rebase_sha=self.anchor,
        )

    def publish_recovered_head(self) -> None:
        """Land the rewritten head the way the interrupted push would have."""
        run_git(
            PUSH, REMOTE_NAME, f"{HEAD_REF}:{BRANCH_REF}", cwd=self.work,
        )
        self._rewind_tracking_ref()

    def advance_remote_out_of_band(self) -> str:
        """Land a commit on the PR branch from outside this worktree."""
        other = self.tmpdir / "other"
        subprocess.run(
            [GIT, "clone", "--branch", BRANCH, str(self.remote), str(other)],
            check=True,
            capture_output=True,
        )
        pushed = commit(other, "hotfix.py", "hotfix\n", "fix: out of band")
        run_git(PUSH, REMOTE_NAME, BRANCH, cwd=other)
        self._rewind_tracking_ref()
        return pushed

    def is_clean(self) -> bool:
        """Whether git sees no modified or untracked paths in the worktree."""
        return not run_git("status", "--porcelain", cwd=self.work).strip()

    def rebase_events(self) -> list[dict]:
        """The `base_rebased` audit records the recovery emitted."""
        return [
            event
            for event in self.gh.recorded_events
            if event.get(EVENT_FIELD) == REBASED_EVENT
        ]

    def _rewind_tracking_ref(self) -> None:
        """Point the tracking ref back at the anchor the crash pinned.

        A push from another clone leaves this worktree's
        `refs/remotes/origin/<branch>` untouched in production; rewinding it
        here is what makes the recovery's own fetch the only thing that can
        discover the current remote head.
        """
        run_git(
            "update-ref",
            f"refs/remotes/{REMOTE_NAME}/{BRANCH}",
            self.anchor,
            cwd=self.work,
        )
