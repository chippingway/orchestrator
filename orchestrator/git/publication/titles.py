# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Subject-prefix inference and PR-title selection.

Both surfaces answer the same question -- what subject line should the
orchestrator write when the agent's own commit subject cannot be reused --
so they share this owner and read the branch history through ``probes``.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from github.Issue import Issue

from orchestrator import config
from orchestrator.git.publication import probes


def _infer_subject_prefix(
    spec: config.RepoSpec, worktree: Path, issue: Issue
) -> str:
    """Fallback `<type>` prefix for an orchestrator-synthesized subject.

    Called only when neither the agent's first commit subject nor the issue
    title already carries a reusable `<prefix>:` form. When a repo-local
    prefix (one outside the Conventional Commits allowlist, e.g. `event:` /
    `career:`) dominates recent base-branch history, reuse it so the
    synthesized subject matches the repo's own style instead of blindly
    defaulting to `feat:`. Otherwise fall back to `fix` for bug-labelled
    issues and `feat` everywhere else.
    """
    counts: Counter[str] = Counter()
    for subject in probes._recent_base_subjects(spec, worktree):
        prefix = probes._subject_prefix(subject)
        if prefix:
            counts[prefix] += 1
    if counts:
        # `most_common` breaks ties by first insertion; subjects arrive
        # newest-first, so the most recent of any tied prefixes wins.
        dominant = counts.most_common(1)[0][0]
        if dominant not in probes._CONVENTIONAL_TYPES:
            return dominant
    label_names = {
        (getattr(issue_label, "name", "") or "").lower()
        for issue_label in (issue.labels or [])
    }
    if {"bug", "fix"} & label_names:
        return "fix"
    return "feat"


def _pr_title_from_commit_or_issue(
    issue: Issue, first_subject: str, fallback_prefix: str = "feat",
) -> str:
    """Pick a PR title (also reused as the squash subject).

    Prefer the agent's first commit subject when it already carries a
    reusable `<prefix>:` form (so the PR title matches the commit history),
    then the issue title when it does, and only otherwise synthesize a
    `<fallback_prefix>: <issue title>` -- `fallback_prefix` comes from
    `_infer_subject_prefix`, so the synthesized form honors the repo's own
    style. Traceability is preserved by the `Resolves #<n>` line in the PR
    body, so the title stays clean.
    """
    subject = (first_subject or "").strip()
    if probes._is_prefixed_subject(subject):
        return subject
    issue_title = (issue.title or "").strip()
    if probes._is_prefixed_subject(issue_title):
        return issue_title
    body = issue_title or f"address issue #{issue.number}"
    return f"{fallback_prefix}: {body}"
