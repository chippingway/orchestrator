# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Small value builders shared by workflow tests."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from orchestrator.github import PinnedState

from tests.support.fakes import FakeGitHubClient, FakePR
from tests.workflow.repo_values import (
    TEST_REPO_SLUG,
    _FAKE_WT,
)


def _iso_hours_ago(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(
        timespec="seconds",
    )


def _manifest(payload: str) -> str:
    return f"```orchestrator-manifest\n{payload}\n```"


def _issue_branch(
    issue_number: int,
    slug: str = TEST_REPO_SLUG,
) -> str:
    return f"orchestrator/{slug.replace('/', '__')}/issue-{issue_number}"


def _fake_worktree(*_args, **_kwargs) -> Path:
    return _FAKE_WT


def _state_with_pr_number(
    github: FakeGitHubClient,
    issue_number: int,
    pr_number: int,
    **extra,
) -> PinnedState:
    seed = {"pr_number": pr_number, **extra}
    github.seed_state(issue_number, **seed)
    return PinnedState(comment_id=None, data=dict(seed))


def _open_pr_for(
    github: FakeGitHubClient,
    *,
    issue_number: int,
    pr_number: int,
    **fields,
) -> FakePR:
    """Register the open pull request a pinned `pr_number` names.

    A number in pinned state with no pull request behind it is a state the
    size gate refuses on every route that pushes onto an existing one: what a
    candidate would take that pull request to cannot be measured against a
    pull request nobody can read, and a closed one has nowhere for the push to
    land. So a stage fixture that publishes seeds the pull request as well as
    the number, and the head it stands on is the whole object id the fake
    already defaults to.
    """
    pull_request = FakePR(
        number=pr_number,
        head_branch=_issue_branch(issue_number),
        **fields,
    )
    github.add_pr(pull_request)
    return pull_request


def _analytics_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
