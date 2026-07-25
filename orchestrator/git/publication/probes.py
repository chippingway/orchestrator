# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Branch inspection: ahead/behind counts and commit-subject reads.

The conventional-subject vocabulary lives here because every subject
predicate is built from it: the Conventional type list, the regex that
matches those types, and the broader repo-local prefix patterns are one
family, so a type added to the list cannot drift from the regex that
recognizes it.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from orchestrator import config
from orchestrator.git import commands

_CONVENTIONAL_TYPES = (
    "feat", "fix", "chore", "docs", "refactor",
    "test", "perf", "build", "ci", "style", "revert",
)

_CONVENTIONAL_TYPES_ALT = "|".join(_CONVENTIONAL_TYPES)

_CONVENTIONAL_RE = re.compile(
    rf"^(?:{_CONVENTIONAL_TYPES_ALT})"
    r"(?:\([^)]+\))?!?:\s+\S",
)

_PREFIXED_RE = re.compile(r"^[a-z][a-z0-9-]*(?:\([^)]+\))?!?:\s+\S")

_PREFIX_TOKEN_RE = re.compile(r"^([a-z][a-z0-9-]*)(?:\([^)]+\))?!?:\s+\S")


def _parse_ahead_behind(parts: list[str]) -> Tuple[int, int]:
    """Parse a two-field `rev-list --left-right --count` line into
    `(ahead, behind)`, letting a non-integer field raise `ValueError`."""
    behind = int(parts[0])
    ahead = int(parts[1])
    return (ahead, behind)


def _branch_ahead_behind(
    spec: config.RepoSpec, worktree: Path, branch: str
) -> Tuple[int, int]:
    """Return `(ahead, behind)` commit counts for HEAD relative to
    `<remote>/<branch>` in `worktree`.

    `ahead` = commits in HEAD not in `<remote>/<branch>` (unpushed local
    work). `behind` = commits in `<remote>/<branch>` not in HEAD (the
    local branch is stale relative to the remote PR head). `(0, 0)`
    means HEAD and the remote-tracking ref are identical.

    The caller must have fetched `<remote>/<branch>` immediately before
    calling so the comparison is against the current remote tip.
    Returns `(0, 0)` on git error so a transient failure does not
    silently re-route the workflow; the caller's subsequent steps
    (the rebase attempt, the push) surface the underlying problem.
    """
    comparison_result = commands._git_hardened(
        "rev-list", "--left-right", "--count",
        f"refs/remotes/{spec.remote_name}/{branch}...HEAD",
        cwd=worktree,
    )
    if comparison_result.returncode != 0:
        return (0, 0)
    parts = (comparison_result.stdout or "").strip().split()
    if len(parts) != 2:
        return (0, 0)
    try:
        return _parse_ahead_behind(parts)
    except ValueError:
        return (0, 0)


def _first_commit_subject(spec: config.RepoSpec, worktree: Path) -> str:
    """Subject line of the oldest commit in `origin/<base>..HEAD`, or ''.

    Used by `_on_commits` to derive a PR title from what the agent actually
    wrote, so the PR title matches the commit history when the subject is
    reusable. Reads the base branch from the spec so a multi-repo deployment
    with mixed default branches (e.g. one repo on `main`, another on
    `master`) compares against the right remote.
    """
    log_result = commands._git(
        "log", "--reverse", "--format=%s",
        f"{spec.remote_name}/{spec.base_branch}..HEAD",
        cwd=worktree,
    )
    if log_result.returncode != 0:
        return ""
    lines = (log_result.stdout or "").splitlines()
    return lines[0].strip() if lines else ""


def _is_conventional_subject(subject: str) -> bool:
    return bool(_CONVENTIONAL_RE.match(subject or ""))


def _is_prefixed_subject(subject: str) -> bool:
    """True if `subject` is a reusable `<token>: <subject>` line.

    Broader than `_is_conventional_subject`: any lowercase prefix counts,
    so a repo-local `event:` / `career:` subject is reused verbatim rather
    than discarded for a synthesized `feat:`.
    """
    return bool(_PREFIXED_RE.match(subject or ""))


def _subject_prefix(subject: str) -> Optional[str]:
    """Bare prefix token of a `<token>[(scope)][!]: ...` subject, or None."""
    prefix_match = _PREFIX_TOKEN_RE.match(subject or "")
    return prefix_match.group(1) if prefix_match else None


def _recent_base_subjects(
    spec: config.RepoSpec, worktree: Path, limit: int = 30
) -> List[str]:
    """Subjects of the most recent non-merge base-branch commits (newest
    first), or `[]` on git error.

    Reads `<remote>/<base>` so the sample reflects the repo's own commit
    history rather than the topic branch under construction. Merge commits
    are excluded so their `Merge pull request #...` subjects don't drown
    out the real prefix style.
    """
    log_result = commands._git(
        "log", "--no-merges", f"--max-count={limit}", "--format=%s",
        f"{spec.remote_name}/{spec.base_branch}",
        cwd=worktree,
    )
    if log_result.returncode != 0:
        return []
    return [
        line.strip()
        for line in (log_result.stdout or "").splitlines()
        if line.strip()
    ]
