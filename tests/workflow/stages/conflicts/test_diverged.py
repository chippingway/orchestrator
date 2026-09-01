# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from orchestrator.git.base_sync import pre_pr as _base_sync_pre_pr
from tests.support.fakes import FakeComment, FakeUser
from tests.workflow.fixtures import (
    _agent,
)
from tests.workflow.stages.conflicts.conflicts_test_support import (
    _ResolvingConflictMixin,
)

CONFLICT_ISSUE = 200

# What the ahead/behind comparison answers once somebody else has pushed to
# the pull request branch.
OVERTAKEN = (0, 2)

# The reply an operator leaves on the park, and who leaves it.
HUMAN_REPLY_ID = 9000
HUMAN_LOGIN = "alice"

DIVERGED_NOTICE = "stale or diverged"

# A park that needs a real human answer, for the case a NEW refusal lands on
# top of one.
AGENT_TIMEOUT = "agent_timeout"

AWAITING_HUMAN = "awaiting_human"
REBASE_SEAM = "_rebase_base_into_worktree"

RUN_AGENT = "run_agent"
PUSH_BRANCH = "_push_branch"


class ResolvingConflictStaleDivergedTest(unittest.TestCase, _ResolvingConflictMixin):
    """Drive `_handle_resolving_conflict` through the conservative
    stale / diverged worktree parks: a worktree behind or diverged from
    `origin/<branch>` must refuse to force-push and park awaiting human.
    """

    def test_stale_worktree_parks_awaiting_human(self) -> None:
        # Worktree behind `origin/<branch>` (someone pushed to the PR
        # branch out-of-band). Force-pushing the local state would
        # clobber the real PR head; refuse and park.
        gh, issue, _ = self._seed()

        merge_mock = MagicMock(return_value=(True, []))

        with patch.object(_base_sync_pre_pr, REBASE_SEAM, merge_mock):
            mocks = self._run_resolving_conflict(
                gh,
                issue,
                run_agent=_agent(),
                push_branch=True,
                branch_ahead_behind=(0, 2),
            )
        merge_mock.assert_not_called()
        mocks["_push_branch"].assert_not_called()
        mocks["run_agent"].assert_not_called()
        self.assertTrue(gh.pinned_data(CONFLICT_ISSUE).get(AWAITING_HUMAN))
        self.assertNotIn((CONFLICT_ISSUE, "workflow:validating"), gh.label_history)
        last_comment = gh.posted_comments[-1][1]
        self.assertIn("stale or diverged", last_comment)

    def test_diverged_worktree_parks_awaiting_human(self) -> None:
        # Both ahead and behind: histories diverged. Cannot safely push
        # without rewriting remote history that may have value.
        gh, issue, _ = self._seed()

        merge_mock = MagicMock(return_value=(True, []))

        with patch.object(_base_sync_pre_pr, REBASE_SEAM, merge_mock):
            mocks = self._run_resolving_conflict(
                gh,
                issue,
                run_agent=_agent(),
                push_branch=True,
                branch_ahead_behind=(1, 1),
            )
        merge_mock.assert_not_called()
        mocks["_push_branch"].assert_not_called()
        state = gh.pinned_data(CONFLICT_ISSUE)
        self.assertTrue(state.get(AWAITING_HUMAN))
        self.assertNotIn((CONFLICT_ISSUE, "workflow:validating"), gh.label_history)


if __name__ == "__main__":
    unittest.main()


class ResolvingConflictDivergedReplyTest(
    unittest.TestCase, _ResolvingConflictMixin,
):
    """A human reply on a branch the remote has moved past.

    The park invites a comment, and for most of this stage's refusals a
    comment is the answer. For this one it is not: what a reply starts is an
    agent whose commit this stage force-pushes, and the checkout it would
    push from never had the commits that moved the remote. So the divergence
    is read before the reply is answered, on this tick and on every one after
    it.
    """

    def test_a_reply_resumes_no_diverged_branch(self) -> None:
        # No lease catches this one: the tip the push is pinned to is the tip
        # the resume just READ, so git has nothing to refuse and the external
        # commits go with the force-push.
        github, mocks = self._replied_to_the_park()

        mocks[RUN_AGENT].assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()
        self.assertNotIn(
            (CONFLICT_ISSUE, "workflow:validating"), github.label_history,
        )
        self.assertTrue(
            github.pinned_data(CONFLICT_ISSUE).get(AWAITING_HUMAN),
        )

    def test_a_bare_reply_resumes_no_diverged_branch(self) -> None:
        # The other door into the same agent. A reply that leaves the drift
        # baseline where it is takes the awaiting-human road instead of the
        # body-edit one, and it is refused by the same reading: the checkout
        # it would resolve in is not what the pull request carries.
        _github, mocks = self._replied_to_the_park(rebaselined=True)

        mocks[RUN_AGENT].assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()

    def test_a_new_refusal_speaks_over_an_older_park(self) -> None:
        # Silence is per REASON, not per park. An issue already waiting on a
        # human for something else -- a question, a timeout -- that then
        # becomes diverged is being told something new, and the guard now
        # blocks the reply it was waiting to give, so saying nothing would
        # strand it with no notice of why.
        github, issue = self._seed(extra_state={
            AWAITING_HUMAN: True, "park_reason": AGENT_TIMEOUT,
        })[:2]

        with patch.object(
            _base_sync_pre_pr, REBASE_SEAM,
            MagicMock(return_value=(True, [])),
        ):
            self._run_resolving_conflict(
                github, issue, run_agent=_agent(), push_branch=True,
                branch_ahead_behind=OVERTAKEN,
            )

        self.assertIn(DIVERGED_NOTICE, github.posted_comments[-1][1])

    def test_the_standing_refusal_is_not_re_announced(self) -> None:
        # The refusal stands in front of the reply, so a branch that stays
        # diverged reaches it every poll -- and what it asks for is the branch
        # reconciled, which repeating brings no closer.
        github = self._replied_to_the_park()[0]

        self.assertEqual(
            [
                body for _, body in github.posted_comments
                if DIVERGED_NOTICE in body
            ],
            [github.posted_comments[0][1]],
        )

    def _replied_to_the_park(self, *, rebaselined: bool = False):
        """Park on a diverged branch, then run the tick a reply arrives on.

        `rebaselined` re-takes the drift baseline over the reply, which is the
        state a body edit already answered leaves behind: the hash covers the
        thread as it stands, so the reply reaches the awaiting-human road
        rather than the body-edit one.
        """
        github, issue = self._seed()[:2]
        merge = MagicMock(return_value=(True, []))
        with patch.object(
            _base_sync_pre_pr, REBASE_SEAM, merge,
        ):
            self._run_resolving_conflict(
                github, issue, run_agent=_agent(), push_branch=True,
                branch_ahead_behind=OVERTAKEN,
            )
            issue.comments.append(FakeComment(
                id=HUMAN_REPLY_ID,
                body="rebased it by hand, carry on",
                user=FakeUser(HUMAN_LOGIN),
            ))
            if rebaselined:
                self._seed_with_baseline_hash(github, issue)
            mocks = self._run_resolving_conflict(
                github, issue, run_agent=_agent(), push_branch=True,
                branch_ahead_behind=OVERTAKEN,
            )
        return github, mocks


if __name__ == "__main__":
    unittest.main()
