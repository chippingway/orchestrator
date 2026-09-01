# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Branch inspection: divergence from a remote tip, and commit-subject reads.

The conventional-subject vocabulary lives here because every subject
predicate is built from it: the Conventional type list, the regex that
matches those types, and the broader repo-local prefix patterns are one
family, so a type added to the list cannot drift from the regex that
recognizes it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

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


@dataclass(frozen=True)
class _BranchDivergence:
    """Where a checkout stands against the remote tip it was compared with.

    One reading rather than two facts read separately, and the commit is why.
    The counts are a CLAIM ABOUT `tip`: "ahead of it and not behind it" is
    what licenses a force-push, and the push is pinned to that same commit.
    Read the ref twice -- once to compare against and once to name -- and
    anything moving it in between (another worker in the same checkout, a
    fetch racing this one) leaves the branch proved against one head and the
    push pinned to another. Where the pull request has moved to the second,
    the lease is satisfied and the force-push lands on top of it. So the ref
    is resolved ONCE and the comparison is taken against that immutable id.

    `readable` is what every caller acts on first, and it is not `(0, 0)`.
    Zero and zero is what an in-sync branch answers; a ref nothing could
    resolve, a comparison git refused, and a count in a shape this cannot
    parse are readings that did not happen at all. Collapsed into "in sync"
    they are how a stale checkout gets rebased, spawned over, and
    force-pushed on evidence nobody took.
    """

    tip: str = ""
    ahead: int = 0
    behind: int = 0
    readable: bool = False

    @classmethod
    def taken(
        cls, spec: config.RepoSpec, worktree: Path, branch: str,
    ) -> "_BranchDivergence":
        """Resolve `<remote>/<branch>` once, then count HEAD against it.

        The caller must have fetched that ref immediately before calling, so
        what is resolved here is the tip the remote had a moment ago.
        """
        tip = cls._resolved_tip(spec, worktree, branch)
        if not tip:
            return cls()
        return cls._counted_against(worktree, tip)

    @classmethod
    def _resolved_tip(
        cls, spec: config.RepoSpec, worktree: Path, branch: str,
    ) -> str:
        """The commit the fetched remote-tracking ref names, or "".

        Read from the ref rather than from the remote: asking the remote
        again would answer about a different moment, and the whole point of
        this reading is to name the one the caller's fetch established.
        """
        resolved = commands._git_hardened(
            "rev-parse", f"refs/remotes/{spec.remote_name}/{branch}",
            cwd=worktree,
        )
        if resolved.returncode != 0:
            return ""
        return (resolved.stdout or "").strip()

    @classmethod
    def _counted_against(
        cls, worktree: Path, tip: str,
    ) -> "_BranchDivergence":
        """HEAD's distance from one immutable commit, or an unreadable one.

        `ahead` is what HEAD has and the tip does not -- unpushed local work.
        `behind` is what the tip has and HEAD does not -- a stale checkout.
        """
        counted = commands._git_hardened(
            "rev-list", "--left-right", "--count", f"{tip}...HEAD",
            cwd=worktree,
        )
        if counted.returncode != 0:
            return cls()
        parts = (counted.stdout or "").strip().split()
        if len(parts) != 2:
            return cls()
        try:
            distance = [int(part) for part in parts]
        except ValueError:
            return cls()
        # `rev-list --left-right` reports the left side first, which is the
        # tip: what it has and HEAD does not is `behind`.
        return cls(
            tip=tip, ahead=distance[1], behind=distance[0], readable=True,
        )


def _branch_divergence(
    spec: config.RepoSpec, worktree: Path, branch: str
) -> _BranchDivergence:
    """How far HEAD stands from the freshly-fetched `<remote>/<branch>` tip.

    The seam every caller reaches this reading through, so a test names one
    owner and the record above keeps the reasoning.
    """
    return _BranchDivergence.taken(spec, worktree, branch)


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


def _subject_prefix(subject: str) -> str | None:
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
