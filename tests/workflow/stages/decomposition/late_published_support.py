# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The publication a late generation was entered ON, seeded for a settlement.

A verdict taken past the first push is a claim about one pull request standing
on one head, and both are recorded on the generation rather than looked up. So
a test about that side seeds the pair together: the record carrying the whole
publication group, and the pull request it names.
"""
from __future__ import annotations

from orchestrator.workflow.late_split.models import LateGeneration

from tests.support.fakes import FakePR, FakePRRef, FakeGitHubClient
from tests.workflow.stages.decomposition.late_test_support import (
    PUBLISHED_BRANCH,
    PUBLISHED_HEAD_SHA,
    PUBLISHED_PR_NUMBER,
    PUBLISHED_SOURCE_STAGE,
    late_generation,
)


def published_generation(
    *, stage: str = PUBLISHED_SOURCE_STAGE, **overrides,
) -> LateGeneration:
    """The same oversized generation, entered on a pull request that exists."""
    return late_generation(**overrides).with_publication(
        stage=stage,
        pr_number=PUBLISHED_PR_NUMBER,
        published_sha=PUBLISHED_HEAD_SHA,
    )


def seed_published_pr(
    github: FakeGitHubClient,
    *,
    head: str = PUBLISHED_HEAD_SHA,
    pr_state: str = "open",
) -> FakePR:
    """Add the pull request a post-publication verdict is measured against."""
    published = FakePR(
        number=PUBLISHED_PR_NUMBER,
        head_branch=PUBLISHED_BRANCH,
        head=FakePRRef(sha=head),
        state=pr_state,
    )
    github.add_pr(published)
    return published
