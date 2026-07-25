# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""HEAD and worktree-state probes that classify a verify command's aftermath.

Both probes read a worktree the agent can write to, so they go through the
command owner rather than assembling their own `git` invocation: the dirty
probe needs the hardened envelope's detached config, and the HEAD probe must
share the same no-prompt envelope so a credential-prompting config cannot
hang a worker.
"""
from __future__ import annotations

from pathlib import Path

from orchestrator.git import commands as _commands


def _head_sha(worktree: Path) -> str:
    """HEAD commit SHA of the worktree, or '' if it cannot be read.

    Used by the validating handler to detect whether a dev-fix codex run
    produced a new commit. _has_new_commits compares against origin/<base>,
    which is already true throughout validating, so we need an absolute SHA
    snapshot instead.
    """
    head_result = _commands._git("rev-parse", "HEAD", cwd=worktree)
    if head_result.returncode != 0:
        return ""
    return (head_result.stdout or "").strip()


def _worktree_dirty_files(worktree: Path) -> list[str]:
    """Paths git considers modified or untracked in the worktree.

    Used to refuse opening a PR when codex committed only part of its work and
    left other modifications behind -- the push would publish an incomplete
    branch. The orchestrator's own scratch (codex's `-o` file) lives outside
    the worktree (a per-spawn tempfile in `codex.run_codex`), so it never
    surfaces here regardless of the target repo's .gitignore.

    Hardened unconditionally: `git status --porcelain` refreshes the index,
    which spawns a configured `core.fsmonitor` helper -- and the agent can
    plant one in the worktree's `.git/config` or in `~/.gitconfig` (same OS
    user), so a plain probe would execute it with the orchestrator's process
    environment (ambient secrets) attached. Every call site is an
    agent-writable worktree, so there is no trusted caller that would want
    the unhardened form. Detaching global/system config also drops a global
    `core.excludesFile` from the untracked filter; the repo's own tracked
    `.gitignore` still applies, which is the intended trust boundary.
    """
    status_result = _commands._git_hardened("status", "--porcelain", cwd=worktree)
    if status_result.returncode != 0:
        return []
    paths: list[str] = []
    for line in (status_result.stdout or "").splitlines():
        if len(line) < 4:
            continue
        # porcelain v1: "XY <path>" with optional " -> dest" for renames.
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        path = rest.strip().strip('"')
        if path:
            paths.append(path)
    return paths
