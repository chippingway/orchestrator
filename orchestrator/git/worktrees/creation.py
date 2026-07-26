# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Issue and PR worktree creation plus the unpushed-work probe they gate on.

Both creators open with the same question -- does the worktree already on
disk still carry commits the orchestrator never pushed? -- and
`_has_new_commits` is the answer. The probe lives beside its only two
callers because the reuse decision and the destructive `worktree remove`
that follows it are one unit; the creators diverge only in which ref a
missing local branch is restored from.
"""
from __future__ import annotations

import logging
from pathlib import Path

from orchestrator import config
from orchestrator.git import authentication, commands, locks
from orchestrator.git.worktrees import paths, recovery

# Named for the historical facade, not this module: operators filter the
# rendered `orchestrator.worktree_lifecycle` prefix and attach handlers to
# that logger, so every owner in this package reports through it.
log = logging.getLogger("orchestrator.worktree_lifecycle")

_WORKTREE_ADD = ("worktree", "add")

_WORKTREE_REMOVE_FORCE = ("worktree", "remove", "--force")


def _ensure_worktree(
    spec: config.RepoSpec, issue_number: int, *, branch: str | None = None,
) -> Path:
    """Return a worktree on a per-issue branch, reusing one with unpushed work.

    The reuse is what lets the orchestrator survive a crash between codex
    committing and the orchestrator pushing -- without it, the next tick would
    wipe the worktree and we'd burn another codex run on the same prompt.

    `branch` overrides the default `_branch_name(spec, issue_number)`
    derivation so callers can anchor on an already-pinned branch (e.g.
    a legacy `orchestrator/issue-<n>` ref kept in pinned state when
    slug-namespacing landed) instead of forcing the issue onto a new
    branch and orphaning its existing PR.

    All git operations target `spec.target_root` and therefore mutate the
    parent clone's `.git/config`. The per-target_root lock (see
    `_target_root_lock`) serializes concurrent workers so two tick fan-out
    threads cannot collide on `.git/config.lock`. The lock is released
    before the caller starts the long-running agent run.
    """
    with locks._target_root_lock(spec.target_root):
        paths._repo_worktrees_root(spec).mkdir(parents=True, exist_ok=True)
        wt = paths._worktree_path(spec, issue_number)
        if branch is None:
            branch = paths._branch_name(spec, issue_number)

        if wt.exists():
            if _has_new_commits(spec, wt):
                log.info(
                    "issue=#%d worktree has unpushed commits; reusing",
                    issue_number,
                )
                return wt
            commands._git(
                *_WORKTREE_REMOVE_FORCE, str(wt),
                cwd=spec.target_root,
            )

        authentication._authed_target_fetch(spec, spec.base_branch)

        have_branch = commands._git(
            "rev-parse", "--verify", branch, cwd=spec.target_root
        ).returncode == 0
        if have_branch:
            worktree_result = commands._git(
                *_WORKTREE_ADD, str(wt), branch, cwd=spec.target_root,
            )
        else:
            worktree_result = commands._git(
                *_WORKTREE_ADD, "-b", branch, str(wt),
                f"{spec.remote_name}/{spec.base_branch}",
                cwd=spec.target_root,
            )
        if worktree_result.returncode != 0:
            raise RuntimeError(
                f"git worktree add failed: {worktree_result.stderr}"
            )
        return wt


def _ensure_pr_worktree(
    spec: config.RepoSpec, issue_number: int, *, branch: str | None = None,
) -> Path:
    """Like `_ensure_worktree`, but restores the local branch from
    `origin/<branch>` when it is missing instead of branching from
    `origin/<base>`.

    `_ensure_worktree`'s fallback (`worktree add -b <branch> ... origin/<base>`)
    is right for a fresh implementing run -- a brand-new PR branch should
    start at the base. It is the WRONG fallback for `_handle_resolving_conflict`:
    once a PR exists, the conflict resolver MUST land on the same branch
    the PR is open against, with the dev's commits intact. A host
    restart, manual cleanup, or `git branch -D` between ticks deletes
    the local ref but leaves the PR's `origin/<branch>` ref alive on
    GitHub; rebuilding off `origin/<base>` would silently discard the
    PR's commits and leave the PR's conflicts unresolved forever.

    All git invocations run from `spec.target_root` (the orchestrator's
    own clone, not the agent-writable worktree) so authenticated fetch
    uses the operator's git config / credential helpers / SSH keys
    directly. The hardening that `_push_branch` applies is unnecessary
    here because nothing in `target_root` is agent-writable.

    Serialized by the per-target_root lock for the same `.git/config.lock`
    reason described on `_ensure_worktree`.
    """
    with locks._target_root_lock(spec.target_root):
        paths._repo_worktrees_root(spec).mkdir(parents=True, exist_ok=True)
        wt = paths._worktree_path(spec, issue_number)
        if branch is None:
            branch = paths._branch_name(spec, issue_number)

        if wt.exists():
            if _has_new_commits(spec, wt):
                log.info(
                    "issue=#%d worktree has unpushed commits; reusing",
                    issue_number,
                )
                return wt
            commands._git(
                *_WORKTREE_REMOVE_FORCE, str(wt),
                cwd=spec.target_root,
            )

        # Fetch both base and the PR's remote branch so either path
        # below has a fresh ref to anchor on. The PR branch fetch is
        # best-effort: a freshly created PR may not have a remote ref
        # yet (the orchestrator's own push opened it), but in that case
        # the local branch must already exist (we just pushed it). Treat
        # fetch failure as non-fatal and let the local ref check below
        # decide. `_authed_target_fetch` already uses the explicit
        # `+refs/heads/<branch>:refs/remotes/<remote>/<branch>` refspec
        # so single-branch / narrowed clones still create the
        # remote-tracking ref the `worktree add ... <remote>/<branch>`
        # fallback anchors on; the `+` prefix forces non-fast-forward
        # update against `--force-with-lease`-rewritten remote tips.
        authentication._authed_target_fetch(spec, spec.base_branch)
        authentication._authed_target_fetch(spec, branch)

        have_local = commands._git(
            "rev-parse", "--verify", branch, cwd=spec.target_root,
        ).returncode == 0
        if have_local:
            worktree_result = commands._git(
                *_WORKTREE_ADD, str(wt), branch, cwd=spec.target_root,
            )
        else:
            # Restore the local branch from the PR's remote head, NOT
            # from `<remote>/<base>` -- the dev's commits live on
            # `<remote>/<branch>` and rebuilding from base would discard
            # them.
            worktree_result = commands._git(
                *_WORKTREE_ADD, "-b", branch, str(wt),
                f"{spec.remote_name}/{branch}",
                cwd=spec.target_root,
            )
        if worktree_result.returncode != 0:
            raise RuntimeError(
                f"git worktree add failed: {worktree_result.stderr}"
            )
        return wt


def _has_new_commits(spec: config.RepoSpec, worktree: Path) -> bool:
    commit_count_result = commands._git(
        "rev-list", "--count",
        f"{spec.remote_name}/{spec.base_branch}..HEAD",
        cwd=worktree,
    )
    if commit_count_result.returncode != 0:
        return False
    return recovery._commit_count_from_stdout(commit_count_result) > 0
