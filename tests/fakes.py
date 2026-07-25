# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable import surface for the in-memory GitHub test doubles.

The doubles live in `tests.support.github`; this module is the flat bridge the
workflow tests reach them through.
"""
from __future__ import annotations

from tests.support.github import client as _client
from tests.support.github import factories as _factories
from tests.support.github import models as _models


FakeGitHubClient = _client.FakeGitHubClient
FakeComment = _models.FakeComment
FakeIssue = _models.FakeIssue
FakeLabel = _models.FakeLabel
FakePR = _models.FakePR
FakePRRef = _models.FakePRRef
FakePRReview = _models.FakePRReview
FakeUser = _models.FakeUser
make_issue = _factories.make_issue
