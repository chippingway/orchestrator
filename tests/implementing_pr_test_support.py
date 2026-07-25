# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures and protocol values for implementing PR tests."""

from __future__ import annotations

from orchestrator import workflow as workflow
from orchestrator.stages import implementing as _implementing
from tests import fakes, implementing_fixing_test_cases, workflow_helpers

implementing = _implementing

FakeComment = fakes.FakeComment
FakeGitHubClient = fakes.FakeGitHubClient
FakePR = fakes.FakePR
FakeUser = fakes.FakeUser
make_issue = fakes.make_issue
IssueScenario = implementing_fixing_test_cases.IssueScenario
posted_comment_contains = implementing_fixing_test_cases.posted_comment_contains

LABEL_IMPLEMENTING = workflow_helpers.LABEL_IMPLEMENTING
_PatchedWorkflowMixin = workflow_helpers._PatchedWorkflowMixin
_TEST_SPEC = workflow_helpers._TEST_SPEC
_agent = workflow_helpers._agent

DEV_SESSION = "sess-1"
DONE_MESSAGE = "done"
FEATURE_PREFIX = "feat"
TEST_ISSUE_TITLE = "add a thing"
TEST_ISSUE_BODY = "please add a thing"
SPARKLY_TITLE = "add a sparkly thing"
SPARKLY_COMMIT_SUBJECT = "feat: add a sparkly thing"
REPO_LOCAL_FORBIDDEN_PREFIXES = ("feat:", "chore:", "refactor:", "test:")
FOREGROUND_MARKER = "NEVER start a background job"
GITHUB_BODY_LIMIT = 65536
EXISTING_PR_NUMBER = 42
FEEDBACK_COMMENT_ID = 42
BRANCHLESS_ISSUE = 11
BRANCHLESS_REPLY_ID = 2100
BRANCHLESS_WATERMARK = 2000
LONG_MESSAGE_WORD_COUNT = 20000
CODE_FENCE_LINE_COUNT = 20000
TOKEN_TAIL_LENGTH = 4000
LONG_BODY_REPEAT_COUNT = 5000
BODY_SHORT_ISSUE = 61
CONVENTIONAL_ISSUE = 30
INFERRED_PREFIX_ISSUE = 37


class _RepoLocalStyleAssertions:
    def _assert_repo_local_style(self, prompt: str) -> None:
        self.assertIn("git log", prompt)
        self.assertIn("repository-local", prompt)
        self.assertIn("event:", prompt)
        self.assertIn("career:", prompt)
        self.assertNotIn("Conventional", prompt)
        for prefix in REPO_LOCAL_FORBIDDEN_PREFIXES:
            self.assertNotIn(prefix, prompt)
        self.assertIn("subject line only", prompt)
        self.assertIn("Co-Authored-By", prompt)


class _ConventionalTitleFixtureMixin(_PatchedWorkflowMixin):
    def _seeded(self, *, issue_number: int = CONVENTIONAL_ISSUE) -> tuple:
        gh = FakeGitHubClient()
        issue = make_issue(
            issue_number,
            label=LABEL_IMPLEMENTING,
            title=SPARKLY_TITLE,
        )
        gh.add_issue(issue)
        return gh, issue
