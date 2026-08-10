# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures and protocol values for implementing retry tests."""

from __future__ import annotations

from unittest import mock

from orchestrator import config
from orchestrator.agents import runner as _agent_runner
from orchestrator.git.worktrees import creation as _worktree_creation
from orchestrator.workflow.stages.implementing import resume as _implementing_resume
from tests.support import fakes
from tests.workflow import fixtures
from tests.workflow.stages import implementing_fixing_test_cases

MagicMock = mock.MagicMock
patch = mock.patch

FakeComment = fakes.FakeComment
FakeGitHubClient = fakes.FakeGitHubClient
FakeUser = fakes.FakeUser
make_issue = fakes.make_issue
IssueScenario = implementing_fixing_test_cases.IssueScenario

BACKEND_CLAUDE = fixtures.BACKEND_CLAUDE
BACKEND_CODEX = fixtures.BACKEND_CODEX
LABEL_DOCUMENTING = fixtures.LABEL_DOCUMENTING
LABEL_IMPLEMENTING = fixtures.LABEL_IMPLEMENTING
LABEL_RESOLVING_CONFLICT = fixtures.LABEL_RESOLVING_CONFLICT
LABEL_VALIDATING = fixtures.LABEL_VALIDATING
REVIEW_APPROVED_MESSAGE = fixtures.REVIEW_APPROVED_MESSAGE
_FAKE_WT = fixtures._FAKE_WT
_PatchedWorkflowMixin = fixtures._PatchedWorkflowMixin
_TEST_SPEC = fixtures._TEST_SPEC
_agent = fixtures._agent
_issue_branch = fixtures._issue_branch
_iso_hours_ago = fixtures._iso_hours_ago

KEY_CODEX_SESSION_ID = "codex_session_id"
KEY_DEV_AGENT = "dev_agent"
KEY_DEV_RESUME_COUNT = "dev_resume_count"
KEY_DEV_SESSION_ID = "dev_session_id"
KEY_RETRY_COUNT = "retry_count"
KEY_SILENT_PARK_COUNT = "silent_park_count"

ENSURE_WORKTREE = "_ensure_worktree"
RUN_AGENT = "run_agent"

# The owners the checkout and the spawn answer on, so a sibling module patches
# the module the stage calls.
agent_runner = _agent_runner
worktree_creation = _worktree_creation
RESUME_SESSION_ID = "resume_session_id"

POISONED_SESSION = "poisoned-sess"
FRESH_SESSION = "fresh-sess"
LIVE_SESSION = "live-sess"
LEGACY_SESSION = "sess-legacy"

IMPLEMENT_PROMPT_FRAGMENT = "implement the thing"
FIX_PROMPT_FRAGMENT = "fix it"
RESUME_PROMPT_FRAGMENT = "resuming work on GitHub issue"
PROMPT_TOO_LONG_MESSAGE = "Prompt is too long"
STALE_SESSION_STDERR = "Error: No conversation found with session ID: poisoned-sess\n"
DEFAULT_SESSION = "sess-1"
DEV_SESSION = "dev-sess"
DONE_MESSAGE = "done"
OK_MESSAGE = "ok"
RESUME_TEXT = "go"

SILENT_SESSION_ISSUE = 950
LEGACY_FRESH_SESSION_ISSUE = 951
STALE_SESSION_ISSUE = 960
OVERFLOW_SESSION_ISSUE = 961
PROACTIVE_SESSION_ISSUE = 962
PREAMBLE_ISSUE = 963
MISSING_SESSION_ISSUE = 964
EMPTY_SESSION_RESULT_ISSUE = 965
FRESH_BACKEND_ISSUE = 20
REVIEW_BACKEND_ISSUE = 21
DEV_FIX_BACKEND_ISSUE = 22
LEGACY_BACKEND_ISSUE = 23
HUMAN_REPLY_ID = 1100
ACTION_COMMENT_ID = 900
EXPIRED_WINDOW_HOURS = 25
HIGH_RESUME_COUNT = 99


class _RetryCapFixtureMixin(_PatchedWorkflowMixin):
    def _seeded(self, **state):
        gh = FakeGitHubClient()
        issue = make_issue(8, label=LABEL_IMPLEMENTING)
        gh.add_issue(issue)
        if state:
            gh.seed_state(8, **state)
        return gh, issue


class _SilentSessionFixtureMixin(_PatchedWorkflowMixin):
    def _seeded_issue(self, *, silent_park_count: int):
        gh = FakeGitHubClient()
        issue = make_issue(SILENT_SESSION_ISSUE, label=LABEL_IMPLEMENTING)
        gh.add_issue(issue)
        gh.seed_state(
            SILENT_SESSION_ISSUE,
            dev_agent=BACKEND_CLAUDE,
            dev_session_id=POISONED_SESSION,
            silent_park_count=silent_park_count,
        )
        return gh, issue


class _StaleSessionFixtureMixin(_PatchedWorkflowMixin):
    def _seeded_issue(self, *, dev_agent: str = BACKEND_CLAUDE):
        gh = FakeGitHubClient()
        issue = make_issue(STALE_SESSION_ISSUE, label=LABEL_RESOLVING_CONFLICT)
        gh.add_issue(issue)
        gh.seed_state(
            STALE_SESSION_ISSUE,
            dev_agent=dev_agent,
            dev_session_id=POISONED_SESSION,
            silent_park_count=0,
        )
        return gh, issue


class _OverflowSessionFixtureMixin(_PatchedWorkflowMixin):
    def _seeded_issue(self, *, dev_agent: str = BACKEND_CLAUDE):
        gh = FakeGitHubClient()
        issue = make_issue(OVERFLOW_SESSION_ISSUE, label=LABEL_IMPLEMENTING)
        gh.add_issue(issue)
        gh.seed_state(
            OVERFLOW_SESSION_ISSUE,
            dev_agent=dev_agent,
            dev_session_id=POISONED_SESSION,
            silent_park_count=0,
        )
        return gh, issue


class _ProactiveSessionFixtureMixin(_PatchedWorkflowMixin):
    def _seeded_issue(
        self,
        *,
        resume_count: int = 0,
        dev_agent: str = BACKEND_CLAUDE,
        sid: str = LIVE_SESSION,
    ):
        gh = FakeGitHubClient()
        issue = make_issue(
            PROACTIVE_SESSION_ISSUE,
            label="in_review",
            body=IMPLEMENT_PROMPT_FRAGMENT,
        )
        gh.add_issue(issue)
        gh.seed_state(
            PROACTIVE_SESSION_ISSUE,
            dev_agent=dev_agent,
            dev_session_id=sid,
            silent_park_count=0,
            dev_resume_count=resume_count,
        )
        return gh, issue

    def _run_resume(self, gh, issue, *, fake_run, threshold):
        state = gh.read_pinned_state(issue)
        with (
            patch.object(config, "DEV_SESSION_MAX_RESUMES", threshold),
            patch.object(
                _worktree_creation, ENSURE_WORKTREE, return_value=_FAKE_WT,
            ),
            patch.object(_agent_runner, RUN_AGENT, fake_run),
        ):
            _, agent_result, _ = _implementing_resume._resume_dev_with_text(
                gh,
                _TEST_SPEC,
                issue,
                state,
                FIX_PROMPT_FRAGMENT,
            )
        return state, agent_result
