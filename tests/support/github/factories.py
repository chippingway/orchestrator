# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Constructors for the in-memory GitHub doubles."""
from __future__ import annotations

from tests.support.github.models import FakeIssue, FakeLabel, FakeUser
from tests.support.github.state import _IssueSeed


def make_issue(number: int, **issue_fields) -> FakeIssue:
    """Build an issue while preserving the historical keyword surface."""
    seed = _IssueSeed(**issue_fields)
    labels = [FakeLabel(seed.label)] if seed.label else []
    return FakeIssue(
        number=number,
        title=seed.title,
        body=seed.body,
        labels=labels,
        comments=list(seed.comments),
        closed=seed.closed,
        user=FakeUser(seed.author),
    )
