# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Tests for implementing terminal closed behavior."""

from __future__ import annotations

import unittest

from tests.workflow.stages.implementing import terminal_test_support as support

CLEANUP_TERMINAL_BRANCH = support.CLEANUP_TERMINAL_BRANCH
CLOSED_PR = support.CLOSED_PR
CLOSED_PR_ISSUE = support.CLOSED_PR_ISSUE
CLOSED_WITHOUT_MERGE_AT = support.CLOSED_WITHOUT_MERGE_AT
DEV_AGENT = support.DEV_AGENT
DEV_SESSION = support.DEV_SESSION
EVENT_PR_CLOSED_WITHOUT_MERGE = support.EVENT_PR_CLOSED_WITHOUT_MERGE
FETCH_FAILURE_ISSUE = support.FETCH_FAILURE_ISSUE
FETCH_FAILURE_PR = support.FETCH_FAILURE_PR
FakeGitHubClient = support.FakeGitHubClient
FakePR = support.FakePR
FakePRRef = support.FakePRRef
LABEL_DONE = support.LABEL_DONE
LABEL_IMPLEMENTING = support.LABEL_IMPLEMENTING
LABEL_REJECTED = support.LABEL_REJECTED
MERGED_DEFER_ISSUE = support.MERGED_DEFER_ISSUE
MERGED_DEFER_PR = support.MERGED_DEFER_PR
MagicMock = support.MagicMock
NO_PR_ISSUE = support.NO_PR_ISSUE
OPEN_PR = support.OPEN_PR
OPEN_PR_ISSUE = support.OPEN_PR_ISSUE
PR_HEAD_SHA = support.PR_HEAD_SHA
RUN_AGENT = support.RUN_AGENT
_PatchedWorkflowMixin = support._PatchedWorkflowMixin
_TEST_SPEC = support._TEST_SPEC
_agent = support._agent
_issue_branch = support._issue_branch
make_issue = support.make_issue


class HandleImplementingClosedIssueTest(unittest.TestCase, _PatchedWorkflowMixin):
    """Closed `implementing` issues yielded by the new closed-issue sweep
    must NOT spawn the dev agent. The handler now flips to `rejected`
    after the external-merge finalize returns False.
    """

    def test_no_pr_flips_to_rejected(self) -> None:
        gh = FakeGitHubClient()
        issue = make_issue(NO_PR_ISSUE, label=LABEL_IMPLEMENTING)
        issue.closed = True
        gh.add_issue(issue)
        gh.seed_state(NO_PR_ISSUE, dev_agent=DEV_AGENT, dev_session_id=DEV_SESSION)

        mocks = self._run_implementing(
            gh,
            issue,
            run_agent=_agent(),
        )

        self.assertIn((NO_PR_ISSUE, LABEL_REJECTED), gh.label_history)
        self.assertIn(CLOSED_WITHOUT_MERGE_AT, gh.pinned_data(NO_PR_ISSUE))
        mocks[RUN_AGENT].assert_not_called()
        # No PR → no branch cleanup (no remote ref to delete).
        mocks[CLEANUP_TERMINAL_BRANCH].assert_not_called()

    def test_open_pr_skips_cleanup(self) -> None:
        gh = FakeGitHubClient()
        issue = make_issue(OPEN_PR_ISSUE, label=LABEL_IMPLEMENTING)
        issue.closed = True
        gh.add_issue(issue)
        pr = FakePR(
            number=OPEN_PR,
            head_branch=_issue_branch(OPEN_PR_ISSUE),
            head=FakePRRef(sha=PR_HEAD_SHA),
            merged=False,
            state="open",
        )
        gh.add_pr(pr)
        gh.seed_state(
            OPEN_PR_ISSUE,
            pr_number=OPEN_PR,
            branch=_issue_branch(OPEN_PR_ISSUE),
            dev_agent=DEV_AGENT,
            dev_session_id=DEV_SESSION,
        )

        mocks = self._run_implementing(
            gh,
            issue,
            run_agent=_agent(),
        )

        self.assertIn((OPEN_PR_ISSUE, LABEL_REJECTED), gh.label_history)
        self.assertIn(CLOSED_WITHOUT_MERGE_AT, gh.pinned_data(OPEN_PR_ISSUE))
        mocks[RUN_AGENT].assert_not_called()
        # Open PR + closed issue: leave the branch alone so the operator
        # can salvage / reopen the PR.
        mocks[CLEANUP_TERMINAL_BRANCH].assert_not_called()

    def test_closed_pr_runs_cleanup(self) -> None:
        gh = FakeGitHubClient()
        issue = make_issue(CLOSED_PR_ISSUE, label=LABEL_IMPLEMENTING)
        issue.closed = True
        gh.add_issue(issue)
        pr = FakePR(
            number=CLOSED_PR,
            head_branch=_issue_branch(CLOSED_PR_ISSUE),
            head=FakePRRef(sha=PR_HEAD_SHA),
            merged=False,
            state="closed",
        )
        gh.add_pr(pr)
        gh.seed_state(
            CLOSED_PR_ISSUE,
            pr_number=CLOSED_PR,
            branch=_issue_branch(CLOSED_PR_ISSUE),
            dev_agent=DEV_AGENT,
            dev_session_id=DEV_SESSION,
        )

        mocks = self._run_implementing(
            gh,
            issue,
            run_agent=_agent(),
        )

        self.assertIn((CLOSED_PR_ISSUE, LABEL_REJECTED), gh.label_history)
        self.assertIn(CLOSED_WITHOUT_MERGE_AT, gh.pinned_data(CLOSED_PR_ISSUE))
        mocks[RUN_AGENT].assert_not_called()
        mocks[CLEANUP_TERMINAL_BRANCH].assert_called_once_with(
            gh,
            _TEST_SPEC,
            CLOSED_PR_ISSUE,
            branch=_issue_branch(CLOSED_PR_ISSUE),
        )
        # `pr_closed_without_merge` event emitted only when the PR
        # itself is closed (mirrors in_review / fixing semantics).
        kinds = [event["event"] for event in gh.recorded_events]
        self.assertIn(EVENT_PR_CLOSED_WITHOUT_MERGE, kinds)

    def test_pr_fetch_error_defers(self) -> None:
        # Both `_pr_terminal_stops_the_tick` and `_finalize_if_issue_closed`
        # need a successful `gh.get_pr` call to act safely on a closed
        # issue with a pinned `pr_number`. If the PR fetch raises, the
        # PR terminal falls through on "could not read" -- nothing about a
        # failed read says which ending, if any, it was hiding; flipping the
        # issue to `rejected` from the closed-issue helper anyway would
        # permanently terminal-label a merged-PR issue whose finalize is
        # just retrying through a transient network blip. So the
        # closed-issue helper defers when its own fetch
        # raises, leaving the issue alone for the next tick.
        gh = FakeGitHubClient()
        issue = make_issue(FETCH_FAILURE_ISSUE, label=LABEL_IMPLEMENTING)
        issue.closed = True
        gh.add_issue(issue)
        # Pin a `pr_number` but DON'T add the PR to `gh.pulls`. The
        # fake's `get_pr` raises `KeyError` when the number is missing,
        # which models the real PyGithub failure surface (any exception
        # from `gh.get_pr` -- transient 5xx, rate limit, network blip).
        gh.seed_state(
            FETCH_FAILURE_ISSUE,
            pr_number=FETCH_FAILURE_PR,
            branch=_issue_branch(FETCH_FAILURE_ISSUE),
            dev_agent=DEV_AGENT,
            dev_session_id=DEV_SESSION,
        )

        mocks = self._run_implementing(
            gh,
            issue,
            run_agent=_agent(),
        )

        self.assertNotIn((FETCH_FAILURE_ISSUE, LABEL_REJECTED), gh.label_history)
        self.assertNotIn((FETCH_FAILURE_ISSUE, LABEL_DONE), gh.label_history)
        self.assertNotIn(
            CLOSED_WITHOUT_MERGE_AT,
            gh.pinned_data(FETCH_FAILURE_ISSUE),
        )
        mocks[RUN_AGENT].assert_not_called()
        mocks[CLEANUP_TERMINAL_BRANCH].assert_not_called()

    def test_merged_pr_defers(self) -> None:
        # Models the race where the PR terminal's own reading failed (so it
        # fell through, saying nothing about either ending) but the PR is
        # actually merged. The closed-issue helper then runs its own fetch
        # successfully, sees the PR merged, and must NOT flip to `rejected`
        # -- the next tick re-enters the merged arc. Otherwise a merged PR's
        # issue would be permanently mis-labeled.
        gh = FakeGitHubClient()
        issue = make_issue(MERGED_DEFER_ISSUE, label=LABEL_IMPLEMENTING)
        issue.closed = True
        gh.add_issue(issue)
        pr = FakePR(
            number=MERGED_DEFER_PR,
            head_branch=_issue_branch(MERGED_DEFER_ISSUE),
            head=FakePRRef(sha=PR_HEAD_SHA),
            merged=True,
            state="closed",
        )
        gh.add_pr(pr)
        gh.seed_state(
            MERGED_DEFER_ISSUE,
            pr_number=MERGED_DEFER_PR,
            branch=_issue_branch(MERGED_DEFER_ISSUE),
            dev_agent=DEV_AGENT,
            dev_session_id=DEV_SESSION,
        )
        # Force the PR terminal off the merged-path
        # `set_workflow_label("done")` write by intercepting
        # `gh.get_pr`: raise on the FIRST call -- the one guarded reading
        # that terminal takes -- so it falls through, and succeed on the
        # SECOND, which is the closed-issue helper's own fetch.
        gh.get_pr = MagicMock(  # type: ignore[assignment]
            side_effect=[
                RuntimeError("simulated transient GitHub failure"),
                pr,
            ]
        )

        mocks = self._run_implementing(
            gh,
            issue,
            run_agent=_agent(),
        )

        # No terminal label flip this tick: the PR terminal fell through
        # and the closed-issue helper deferred. The next tick's reading
        # succeeds and runs the proper merged-path cleanup.
        self.assertNotIn((MERGED_DEFER_ISSUE, LABEL_REJECTED), gh.label_history)
        self.assertNotIn((MERGED_DEFER_ISSUE, LABEL_DONE), gh.label_history)
        self.assertNotIn(
            CLOSED_WITHOUT_MERGE_AT,
            gh.pinned_data(MERGED_DEFER_ISSUE),
        )
        self.assertNotIn("merged_at", gh.pinned_data(MERGED_DEFER_ISSUE))
        mocks[RUN_AGENT].assert_not_called()
        mocks[CLEANUP_TERMINAL_BRANCH].assert_not_called()
