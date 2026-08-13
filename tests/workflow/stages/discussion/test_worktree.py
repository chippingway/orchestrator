# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which restorer rebuilds the checkout a discussion round reads.

Both restorers reuse a worktree that is already on disk, so the choice only
shows itself once the local ref is gone -- a host restart, an operator's
cleanup, a `git branch -D` between ticks. From there they disagree about where
the branch comes back from: the base branch, which is right for an issue that
has never been published, or the PR head, which is the only correct answer once
a PR is open against it. Getting that wrong is silent -- the round discusses a
tree the issue is no longer on, and the anchor written straight after certifies
the truncated tip as what the branch arrived carrying.
"""

from __future__ import annotations

import unittest

from tests.workflow.fixtures import (
    _TEST_SPEC,
    _agent,
)

from tests.workflow.stages.discussion.discussion_test_support import (
    DISCUSSION_RESPONSE,
    ENSURE_PR_WORKTREE,
    ENSURE_WORKTREE,
    _DiscussionWorkflowMixin,
    _issue_branch,
    _seed_discussion,
)

_PR_BACKED_ISSUE_NUMBER = 916
_LEGACY_PR_ISSUE_NUMBER = 917
_DISCUSSION_PR_NUMBER = 4242


class DiscussionRoundWorktreeTest(unittest.TestCase, _DiscussionWorkflowMixin):

    def test_a_pr_backed_round_restores_from_the_pr(self) -> None:
        # The issue reached discussion from a PR stage, so the branch under
        # discussion is the one its PR is open against. Rebuilding a pruned
        # local ref from `origin/<base>` would drop the dev's commits out of
        # the tree the decomposer reads and out of the anchor it records.
        gh, issue = _seed_discussion(_PR_BACKED_ISSUE_NUMBER)
        gh.seed_state(
            issue.number,
            branch=_issue_branch(issue.number),
            pr_number=_DISCUSSION_PR_NUMBER,
        )

        mocks = self._run_discussion(
            gh,
            issue,
            run_agent=_agent(last_message=DISCUSSION_RESPONSE),
        )

        mocks[ENSURE_PR_WORKTREE].assert_called_once_with(
            _TEST_SPEC,
            issue.number,
            branch=_issue_branch(issue.number),
        )
        mocks[ENSURE_WORKTREE].assert_not_called()
        self.assert_worktree_preserved(mocks)

    def test_the_pr_restore_targets_the_pinned_branch(self) -> None:
        # A long-lived PR can be open against the legacy `orchestrator/issue-N`
        # ref, and it is that ref the remote head lives on. Restoring the
        # slug-namespaced name instead would branch from a remote ref the PR
        # never wrote to.
        gh, issue = _seed_discussion(_LEGACY_PR_ISSUE_NUMBER)
        legacy_branch = _issue_branch(issue.number, legacy=True)
        gh.seed_state(issue.number, pr_number=_DISCUSSION_PR_NUMBER)

        mocks = self._run_discussion(
            gh,
            issue,
            run_agent=_agent(last_message=DISCUSSION_RESPONSE),
        )

        mocks[ENSURE_PR_WORKTREE].assert_called_once_with(
            _TEST_SPEC, issue.number, branch=legacy_branch,
        )
        mocks[ENSURE_WORKTREE].assert_not_called()

    def test_no_pr_restores_from_the_base_branch(self) -> None:
        # Nothing has been published, so there is no remote head to anchor on
        # and the PR restorer's `worktree add ... <remote>/<branch>` fallback
        # would fail outright. The choice is made on `pr_number` for that
        # reason rather than by probing for the ref.
        gh, issue = _seed_discussion(_PR_BACKED_ISSUE_NUMBER)

        mocks = self._run_discussion(
            gh,
            issue,
            run_agent=_agent(last_message=DISCUSSION_RESPONSE),
        )

        mocks[ENSURE_WORKTREE].assert_called_once_with(
            _TEST_SPEC,
            issue.number,
            branch=_issue_branch(issue.number),
        )
        mocks[ENSURE_PR_WORKTREE].assert_not_called()


if __name__ == "__main__":
    unittest.main()
