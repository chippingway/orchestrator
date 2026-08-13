# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""`read_only_relabel.py` screening a `discussion` park on the way in.

A read-only park is opaque to this stage's resume path, so an operator's
relabel has to be read as an unblock signal -- but only after the checkout is
looked at. A discussion agent that committed left work on the per-issue branch
that nobody reviewed, and the fresh-spawn path's recovered-worktree shortcut
would push it as a dev implementation and open a PR for it.

The guard serves both read-only stages, and the branch exercised here is the
one only a discussion can reach: it may open on a branch that already carries
a PR's commits, so ahead-of-base cannot be the question and the round anchor
is consulted instead. The question stage's half, whose contract forbids
finishing on a branch carrying anything, is covered from
`tests/workflow/stages/question/`. What the tick does once the guard has said
yes is `test_read_only_handoff.py`.
"""

from __future__ import annotations

import unittest

from tests.workflow.fixtures import (
    KEY_AWAITING_HUMAN,
    KEY_PARK_REASON,
    _PatchedWorkflowMixin,
    _agent,
    _issue_branch,
)

from tests.workflow.stages.implementing.read_only_relabel_test_support import (
    DEV_SESSION,
    HEAD_AFTER_COMMIT,
    HEAD_BEFORE_ROUND,
    KEY_ROUND_SHA,
    PARK_DISCUSSION_COMMITS,
    PARK_DISCUSSION_RESPONSE,
    PARK_DISCUSSION_UNSAFE_RELABEL,
)
from tests.workflow.stages.implementing.read_only_relabel_test_support import (
    PUSH_BRANCH,
    RUN_AGENT,
    UNEXPECTED_AGENT_MESSAGE,
    _ReadOnlyRelabelMixin,
    _seed_relabeled_discussion,
)

_UNSAFE_RELABEL_ISSUE_NUMBER = 990
_SAFE_RELABEL_ISSUE_NUMBER = 991
_INHERITED_RELABEL_ISSUE_NUMBER = 992
_MOVED_TIP_RELABEL_ISSUE_NUMBER = 993
_RESET_RELABEL_ISSUE_NUMBER = 994
_RESET_TO_BASE_ISSUE_NUMBER = 998
_VANISHED_REF_ISSUE_NUMBER = 999
_BASE_TIP = "head-at-the-base-branch"
# The two ways the recorded ref stops matching its anchor: moved past it by a
# commit, and dragged back to base by an over-broad reset.
_UNCERTIFIED_TIPS = (
    (_MOVED_TIP_RELABEL_ISSUE_NUMBER, HEAD_AFTER_COMMIT),
    (_RESET_TO_BASE_ISSUE_NUMBER, _BASE_TIP),
)
# The two ways a branch ends a discussion ahead of base but unmoved by it:
# never written to, and written to then reset back to the anchor.
_CERTIFIED_TIP_PARKS = (
    (_INHERITED_RELABEL_ISSUE_NUMBER, PARK_DISCUSSION_RESPONSE),
    (_RESET_RELABEL_ISSUE_NUMBER, PARK_DISCUSSION_COMMITS),
)


class DiscussionRelabelToImplementingTest(
    unittest.TestCase, _PatchedWorkflowMixin, _ReadOnlyRelabelMixin,
):

    def test_a_committed_park_refuses_the_relabel(self) -> None:
        # The discussion agent committed and the stage parked on it, leaving
        # the anchor standing. The relabel must not become the route by which
        # that commit is pushed and a PR opened for it -- and the refusal has
        # to name the anchor as the reset target, because on a PR-backed issue
        # "reset to base" would throw the PR's commits away with the agent's.
        gh, issue = _seed_relabeled_discussion(
            _UNSAFE_RELABEL_ISSUE_NUMBER, PARK_DISCUSSION_COMMITS,
        )

        mocks = self._run_implementing_on_worktree(
            gh,
            issue,
            unpushed_branch=_issue_branch(issue.number),
            run_agent=_agent(last_message=UNEXPECTED_AGENT_MESSAGE),
            has_new_commits=True,
            branch_tip_sha=HEAD_AFTER_COMMIT,
        )

        mocks[RUN_AGENT].assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()
        self.assertEqual(gh.opened_prs, [])
        pinned_data = gh.pinned_data(issue.number)
        self.assertTrue(pinned_data[KEY_AWAITING_HUMAN])
        self.assertEqual(
            pinned_data[KEY_PARK_REASON], PARK_DISCUSSION_UNSAFE_RELABEL,
        )
        refusal = gh.posted_comments[-1][1]
        self.assertIn("discussion agent must be read-only", refusal)
        self.assertIn(HEAD_BEFORE_ROUND, refusal)
        self.assertNotIn("branch -D", refusal)

    def test_a_branch_still_on_the_anchor_relabels(self) -> None:
        # A branch ahead of base that this stage did not move, from both
        # directions. `discussion_response` is the issue that reached the
        # stage from a PR and was only ever read; `discussion_commits` is the
        # same issue after the agent committed and an operator reset back to
        # the anchor, which drops that commit and keeps the PR's underneath.
        # Asking "is this branch ahead of base" would refuse both over the
        # dev's own earlier work, and the second would have no way out that
        # did not also destroy the PR.
        for issue_number, park_reason in _CERTIFIED_TIP_PARKS:
            with self.subTest(park_reason=park_reason):
                self._assert_relabel_allowed(issue_number, park_reason)

    def test_a_tip_off_the_anchor_refuses_the_relabel(self) -> None:
        # The recorded ref is compared to the recorded SHA whatever it now
        # stands in relation to base, because ahead-of-base answers neither
        # end of this. A tip past the anchor is the agent's commit. A tip
        # reset all the way TO base is not ahead of base at all, so the cheap
        # question calls it clean -- while on the PR-backed issue this park
        # exists for, that reset threw away the commits the round was
        # certified against and the violation went unresolved.
        for issue_number, tip in _UNCERTIFIED_TIPS:
            with self.subTest(tip=tip):
                self._assert_relabel_refused(issue_number, tip)

    def test_a_vanished_ref_is_not_a_violation(self) -> None:
        # No local branch means nothing local to attribute: this stage never
        # pushes, so a PR-backed checkout is rebuilt from the PR head, which
        # never carried its work. Convicting here would strand the pruned
        # -worktree recovery an operator has no way to undo.
        gh, issue = _seed_relabeled_discussion(
            _VANISHED_REF_ISSUE_NUMBER, PARK_DISCUSSION_RESPONSE,
        )

        mocks = self._run_implementing_on_worktree(
            gh,
            issue,
            unpushed_branch=None,
            run_agent=_agent(session_id=DEV_SESSION, last_message="implemented"),
            has_new_commits=[False, True],
            branch_tip_sha="",
            head_shas=(HEAD_BEFORE_ROUND, HEAD_AFTER_COMMIT),
        )

        mocks[RUN_AGENT].assert_called_once()
        self.assertNotEqual(
            gh.pinned_data(issue.number).get(KEY_PARK_REASON),
            PARK_DISCUSSION_UNSAFE_RELABEL,
        )

    def test_a_clean_park_lets_the_dev_run(self) -> None:
        # The ordinary exit: the humans settled the design, the tree is clean,
        # and the relabel IS the unblock signal. The park is dropped and the
        # dev spawns fresh rather than resuming a discussion nobody is having.
        gh, issue = _seed_relabeled_discussion(
            _SAFE_RELABEL_ISSUE_NUMBER, PARK_DISCUSSION_RESPONSE,
        )

        mocks = self._run_implementing_on_worktree(
            gh,
            issue,
            unpushed_branch=None,
            run_agent=_agent(session_id=DEV_SESSION, last_message="implemented"),
            has_new_commits=[False, True],
            head_shas=(HEAD_BEFORE_ROUND, HEAD_AFTER_COMMIT),
        )

        mocks[RUN_AGENT].assert_called_once()
        self.assertIn("You are the implementer", mocks[RUN_AGENT].call_args.args[1])
        self.assertEqual(len(gh.opened_prs), 1)
        pinned_data = gh.pinned_data(issue.number)
        self.assertFalse(pinned_data.get(KEY_AWAITING_HUMAN))
        self.assertIsNone(pinned_data.get(KEY_PARK_REASON))

    def _assert_relabel_refused(self, issue_number: int, tip: str) -> None:
        gh, issue = _seed_relabeled_discussion(
            issue_number, PARK_DISCUSSION_RESPONSE,
        )

        mocks = self._run_implementing_on_worktree(
            gh,
            issue,
            # None is the shape a reset-to-base branch reports: nothing is
            # ahead of base any more, so the guard has only the anchor left.
            unpushed_branch=(
                _issue_branch(issue.number) if tip == HEAD_AFTER_COMMIT else None
            ),
            run_agent=_agent(last_message=UNEXPECTED_AGENT_MESSAGE),
            has_new_commits=tip == HEAD_AFTER_COMMIT,
            branch_tip_sha=tip,
        )

        mocks[RUN_AGENT].assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()
        self.assertEqual(gh.opened_prs, [])
        self.assertEqual(
            gh.pinned_data(issue.number)[KEY_PARK_REASON],
            PARK_DISCUSSION_UNSAFE_RELABEL,
        )

    def _assert_relabel_allowed(self, issue_number: int, park_reason: str) -> None:
        """One certified-tip relabel: the dev runs and the park is dropped.

        `has_new_commits` is True throughout, which is the only setting
        consistent with the ahead-of-base branch this scenario is about --
        both probes count commits against `<remote>/<base>`, so a branch the
        guard sees carrying commits is one the spawn path sees carrying them
        too. Letting it answer False would hide the whole defect: the guard
        would certify the branch and the recovered-worktree shortcut would
        then skip the implementer and republish those commits as its work.
        """
        gh, issue = _seed_relabeled_discussion(issue_number, park_reason)

        mocks = self._run_implementing_on_worktree(
            gh,
            issue,
            unpushed_branch=_issue_branch(issue.number),
            run_agent=_agent(session_id=DEV_SESSION, last_message="implemented"),
            has_new_commits=True,
            branch_tip_sha=HEAD_BEFORE_ROUND,
            head_shas=(HEAD_BEFORE_ROUND, HEAD_AFTER_COMMIT),
        )

        mocks[RUN_AGENT].assert_called_once()
        self.assertIn("You are the implementer", mocks[RUN_AGENT].call_args.args[1])
        pinned_data = gh.pinned_data(issue.number)
        self.assertNotEqual(
            pinned_data.get(KEY_PARK_REASON), PARK_DISCUSSION_UNSAFE_RELABEL,
        )
        self.assertFalse(pinned_data.get(KEY_AWAITING_HUMAN))
        # The anchor goes with the park: the branch is the dev's from here.
        self.assertIsNone(pinned_data.get(KEY_ROUND_SHA))


if __name__ == "__main__":
    unittest.main()
