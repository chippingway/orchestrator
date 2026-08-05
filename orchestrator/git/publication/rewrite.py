# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The destructive half of a squash: reset, recommit, publish, roll back.

Every step here runs after the branch has already been rewound, so each
failure path restores `plan.original_head` before reporting -- the agent's
commits stay on the branch and a human decides what to do next. The same
pinned SHA is the force-push lease, so a remote that moved underneath the
rewrite rejects the push instead of losing the update.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from github.Issue import Issue

from orchestrator import config
from orchestrator.git import authentication, commands
from orchestrator.git.publication import planning
from orchestrator.git.verification import probes as verification_probes

# The channel is named for the branch-publication domain rather than for this
# module's path: operators filter the rendered `orchestrator.branch_publication`
# prefix and attach handlers to it, so a squash reports where their filters
# already point whichever owner here is the one emitting.
log = logging.getLogger("orchestrator.branch_publication")


def _squash_failure(
    error: str,
) -> Tuple[bool, Optional[str], int, Optional[str]]:
    """Return the uniform failure result while leaving commits intact."""
    return False, None, 0, error


def _squash_commit_env() -> dict[str, str]:
    """Return the hardened agent identity used for the squash commit."""
    return {
        **os.environ,
        **commands._GIT_NO_PROMPT_ENV,
        "GIT_AUTHOR_NAME": config.AGENT_GIT_NAME,
        "GIT_AUTHOR_EMAIL": config.AGENT_GIT_EMAIL,
        "GIT_COMMITTER_NAME": config.AGENT_GIT_NAME,
        "GIT_COMMITTER_EMAIL": config.AGENT_GIT_EMAIL,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def _rollback_squash(
    plan: planning._SquashPlan,
    worktree: Path,
    issue: Issue,
    reason: str,
    error: str,
) -> Tuple[bool, Optional[str], int, Optional[str]]:
    """Restore the original branch after a post-reset failure."""
    rollback_result = commands._git_hardened(
        "reset", "--hard", plan.original_head, cwd=worktree,
    )
    if rollback_result.returncode != 0:
        log.error(
            "issue=#%s rollback to %s after %s failed; worktree may be "
            "in an inconsistent state: %s",
            issue.number,
            plan.original_head,
            reason,
            (rollback_result.stderr or "").strip(),
        )
    return _squash_failure(error)


def _create_squash_commit(
    worktree: Path, message: str,
) -> subprocess.CompletedProcess:
    """Create the orchestrator-owned commit with hooks and signing disabled."""
    return subprocess.run(
        [
            "git",
            "-c", "core.hooksPath=/dev/null",
            "-c", "core.fsmonitor=",
            "-c", "commit.gpgsign=false",
            "commit", "-m", message,
        ],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        env=_squash_commit_env(),
    )


def _rewrite_squash(
    spec: config.RepoSpec,
    worktree: Path,
    branch: str,
    issue: Issue,
    plan: planning._SquashPlan,
) -> Tuple[bool, Optional[str], int, Optional[str]]:
    """Apply a prepared squash and force-publish it with a pinned lease."""
    reset_result = commands._git_hardened(
        "reset", "--soft", plan.base_sha, cwd=worktree,
    )
    if reset_result.returncode != 0:
        detail = (reset_result.stderr or "").strip()
        return _squash_failure(f"reset --soft failed: {detail}")

    commit_result = _create_squash_commit(worktree, plan.message)
    if commit_result.returncode != 0:
        detail = (commit_result.stderr or "").strip()
        return _rollback_squash(
            plan,
            worktree,
            issue,
            "squash commit",
            f"squash commit failed: {detail}",
        )

    new_sha = verification_probes._head_sha(worktree)
    if not new_sha:
        return _rollback_squash(
            plan,
            worktree,
            issue,
            "post-commit head read",
            "could not read new HEAD after squash",
        )
    if not authentication._push_branch(
        spec, worktree, branch, force_with_lease=plan.original_head,
    ):
        return _rollback_squash(
            plan,
            worktree,
            issue,
            "force-push",
            "force-push with lease rejected (concurrent update on the "
            "remote, or lease violation); see orchestrator logs",
        )
    return True, new_sha, len(plan.subjects), None
