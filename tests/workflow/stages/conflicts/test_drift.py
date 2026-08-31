# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest


from tests.support.fakes import (
    DEFAULT_PR_HEAD_SHA,
    FakeGitHubClient,
    FakePR,
    make_issue,
)
from tests.workflow.fixtures import (
    MEASURED_CANDIDATE_SHA,
    _PatchedWorkflowMixin,
    _agent,
    _issue_branch,
)

# The head this stage reads before the resume and the one it leaves the
# checkout at. The second IS the commit the size gate proves that checkout to,
# because in production the two are one read of one worktree: the route names
# the commit it means to publish and the gate refuses a checkout standing
# anywhere else.
BEFORE_SHA = DEFAULT_PR_HEAD_SHA
RESOLVED_SHA = MEASURED_CANDIDATE_SHA

DRIFT_ISSUE = 500
DRIFT_PR = 5000
INTERRUPTED_ISSUE = 501
INTERRUPTED_PR = 5001
DEV_SESSION = "dev-sess"


def _seed_drift_case(issue_number: int, pr_number: int):
    github = FakeGitHubClient()
    issue = make_issue(
        issue_number,
        label="workflow:resolving_conflict",
        body="updated body",
    )
    github.add_issue(issue)
    github.add_pr(FakePR(number=pr_number, head_branch=_issue_branch(issue_number)))
    github.seed_state(
        issue_number,
        pr_number=pr_number,
        dev_agent="claude",
        dev_session_id=DEV_SESSION,
        conflict_round=0,
        branch=_issue_branch(issue_number),
        user_content_hash="stale-hash",
    )
    return github, issue


def _assert_interrupted_drift_state(test_case, github) -> None:
    state = github.pinned_data(INTERRUPTED_ISSUE)
    test_case.assertEqual(state.get("user_content_hash"), "stale-hash")
    test_case.assertFalse(state.get("awaiting_human"))
    test_case.assertEqual(state.get("conflict_round"), 0)
    test_case.assertNotIn((INTERRUPTED_ISSUE, "workflow:validating"), github.label_history)
    test_case.assertFalse(
        any(
            "agent needs your input" in body or "existing work" in body or "timed out" in body
            for _, body in github.posted_comments
        )
    )


class HandleResolvingConflictHashDriftTest(
    unittest.TestCase,
    _PatchedWorkflowMixin,
):
    """Reviewer point 2: `resolving_conflict` is dispatched per tick too,
    so a body edit while the dev is resolving conflicts must surface to
    the dev. Mirrors the in_review pattern: post a PR notice and resume."""

    def test_drift_posts_pr_notice_and_resumes_dev(self) -> None:
        gh, issue = _seed_drift_case(DRIFT_ISSUE, DRIFT_PR)

        self._run_resolving_conflict(
            gh,
            issue,
            run_agent=_agent(session_id=DEV_SESSION, last_message="resolved with edit"),
            has_new_commits=True,
            dirty_files=(),
            push_branch=True,
            # Two SHAs, and the second is read once: the head the resume
            # produced is what the publication measures, what a hold would
            # name its round by, and what the `conflict_round` audit emit
            # records, so one reading travels to all three.
            head_shas=[BEFORE_SHA, RESOLVED_SHA],
        )

        # Pushed drift fix -> hand straight back to `validating`; the
        # single docs pass is deferred to the post-approval hop.
        self.assertIn((DRIFT_ISSUE, "workflow:validating"), gh.label_history)
        self.assertNotIn((DRIFT_ISSUE, "workflow:documenting"), gh.label_history)
        # Notice posted on the PR.
        self.assertTrue(
            any(
                "issue body changed" in body
                for _, body in gh.posted_pr_comments
            )
        )

    def test_interrupted_resume_keeps_state(self) -> None:
        # The drift resume routes through the shared
        # `_post_user_content_change_result`, which has no interrupted check
        # of its own. The conflicts caller must short-circuit BEFORE it so a
        # shutdown-sweep-killed run cannot ACK / park off partial output and
        # then persist the consumed-comment / refreshed-hash changes.
        gh, issue = _seed_drift_case(INTERRUPTED_ISSUE, INTERRUPTED_PR)
        before_writes = gh.write_state_calls

        mocks = self._run_resolving_conflict(
            gh,
            issue,
            run_agent=_agent(
                session_id=DEV_SESSION,
                last_message="",
                interrupted=True,
            ),
            has_new_commits=True,
            push_branch=True,
            head_shas=[BEFORE_SHA, RESOLVED_SHA],
        )

        # The drift resume spawned, then was seen interrupted.
        mocks["run_agent"].assert_called_once()
        mocks["_push_branch"].assert_not_called()
        # No durable state churn: the refreshed `user_content_hash`,
        # consumed-comment, and session mutations are all discarded.
        self.assertEqual(gh.write_state_calls, before_writes)
        _assert_interrupted_drift_state(self, gh)


if __name__ == "__main__":
    unittest.main()
