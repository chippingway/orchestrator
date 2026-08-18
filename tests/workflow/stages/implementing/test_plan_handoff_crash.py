# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the humans do to the plan PR after the handoff was already accepted.

That write lands before the developer runs, and everything the tick stages
after it is dropped by an interruption on purpose -- a live pause, a shutdown
sweep, a process that simply died. So an issue can sit in the accepted state
for polls at a time, and through all of them the design is still on an open
pull request its reviewers can move.

The records the handoff left describe that PR as it was at the moment of the
write, and nothing was watching it after. Read against a head the humans moved
since, the recorded commit says the PR stopped being a plan -- so a merge of
their own amendment closes the issue as `done` with no developer having run,
and an unmerged one spawns the developer on the checkout the handoff left,
whose ordinary push takes the amendment back out. A merge alone is enough
without any amendment: the baseline that says the handoff is unspent is also
what freezes base sync, so the developer starts behind a base the plan has just
landed in.

What ends the state is the branch and not a record, because a push writes to
git before it writes to the issue: pinned state persisted after one is exactly
what the crash this exists for takes. A tip past the baseline is a developer's
work and none of this applies to it; a tip nothing could read is no answer at
all, and the tick holds rather than deciding the plan question on it.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.workflow.fixtures import BASE_TIP_SHA, LABEL_DONE, _agent

from tests.workflow.stages.implementing.plan_handoff_test_support import (
    AMENDED_PLAN_COMMIT,
    PLAN_COMMIT,
    _HandoffTickMixin,
    _seed_accepted_handoff,
)
from tests.workflow.stages.implementing.read_only_relabel_test_support import (
    ANCHOR_PR_WORKTREE,
    KEY_HANDOFF_ANCHOR,
    KEY_PLAN_SHA,
    KEY_READ_ONLY_BASELINE,
    PUSH_BRANCH,
)

_AMENDED_AFTER_HANDOFF_ISSUE_NUMBER = 1016
_MERGED_AMENDMENT_ISSUE_NUMBER = 1017
_MERGED_AFTER_HANDOFF_ISSUE_NUMBER = 1018
_UNREADABLE_TIP_ISSUE_NUMBER = 1019
_CRASHED_ANCHOR_ISSUE_NUMBER = 1020

_ONTO_THE_BASE = ""
_HEAD_ARG = "head_sha"
_CRASH = "the process died between the anchor and its record"


class _WriteFailsAfterTheAnchor:
    """A pinned write that lands once and then dies.

    The marker's write is the first the reconcile makes and the one recording
    where the branch landed is the second, so failing the second is exactly the
    crash between moving the ref and saying where it was moved to.
    """

    def __init__(self, write) -> None:
        self._write = write
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError(_CRASH)
        return self._write(*args, **kwargs)


# The two ways the design lands while the issue waits: merged as it was
# published, and merged with the reviewers' own correction on it. The second is
# the one that closes the issue on a document; both leave the developer behind
# a base the plan has just landed in.
_MERGED_HEADS = (
    (_MERGED_AFTER_HANDOFF_ISSUE_NUMBER, PLAN_COMMIT),
    (_MERGED_AMENDMENT_ISSUE_NUMBER, AMENDED_PLAN_COMMIT),
)


class CrashedHandoffReconcileTest(unittest.TestCase, _HandoffTickMixin):
    """An accepted handoff caught up to its plan PR before anything runs."""

    def test_an_amendment_after_it_is_inherited(self) -> None:
        # The reviewers corrected the Markdown once the issue was already
        # handed over. Left alone, plan identity reads their head against the
        # recorded commit, calls the PR an implementation, and the developer
        # runs from the retained checkout -- whose push takes the correction
        # back out.
        gh, amended = _seed_accepted_handoff(
            _AMENDED_AFTER_HANDOFF_ISSUE_NUMBER,
            head_sha=AMENDED_PLAN_COMMIT,
            merged=False,
        )

        # Interrupted, so what is read back is the reconcile's own write and
        # nothing the run staged after it.
        mocks = self._interrupted_tick(gh, amended)

        self.assertEqual(
            mocks[ANCHOR_PR_WORKTREE].call_args.kwargs[_HEAD_ARG],
            AMENDED_PLAN_COMMIT,
        )
        self._assert_dev_ran(mocks)
        pinned_data = gh.pinned_data(amended.number)
        self.assertEqual(
            (pinned_data[KEY_PLAN_SHA], pinned_data[KEY_READ_ONLY_BASELINE]),
            (AMENDED_PLAN_COMMIT, AMENDED_PLAN_COMMIT),
        )

    def test_a_merge_after_it_builds_at_base(self) -> None:
        for issue_number, head_sha in _MERGED_HEADS:
            with self.subTest(head=head_sha):
                self._assert_merged_plan_builds(issue_number, head_sha)

    def test_an_unreadable_tip_holds_the_reconcile(self) -> None:
        # Whether the developer has committed is a question only the branch
        # answers -- pinned state written after a push is lost by the very
        # crash this handles. A tip nothing could read is not "no commits", so
        # nothing here decides the plan question or spawns anybody on it.
        gh, unreadable = _seed_accepted_handoff(
            _UNREADABLE_TIP_ISSUE_NUMBER, head_sha=AMENDED_PLAN_COMMIT,
        )
        writes_before = gh.write_state_calls

        mocks = self._run_handoff_tick(gh, unreadable, branch_tip_sha="")

        self._assert_nothing_ran(mocks)
        mocks[ANCHOR_PR_WORKTREE].assert_not_called()
        self.assertEqual(gh.write_state_calls, writes_before)
        self.assertNotIn((unreadable.number, LABEL_DONE), gh.label_history)

    def test_a_crash_inside_the_move_recovers(self) -> None:
        # The move itself has a window: the ref is put on the reviewers' head
        # before anything records that it was. Judged by the branch alone, what
        # that leaves is a tip past the baseline -- which reads as a developer
        # having committed, and hands their amendment to the recovered-work
        # shortcut to push with no agent ever running.
        gh, crashed = _seed_accepted_handoff(
            _CRASHED_ANCHOR_ISSUE_NUMBER,
            head_sha=AMENDED_PLAN_COMMIT,
            merged=False,
        )

        with patch.object(
            gh,
            "write_pinned_state",
            side_effect=_WriteFailsAfterTheAnchor(gh.write_pinned_state),
        ):
            with self.assertRaises(RuntimeError):
                self._run_handoff_tick(gh, crashed)

        # What the crash left: the branch on their head, the records still
        # naming the commit before it, and the marker that tells them apart.
        pinned_data = gh.pinned_data(crashed.number)
        self.assertEqual(
            (
                pinned_data[KEY_HANDOFF_ANCHOR],
                pinned_data[KEY_READ_ONLY_BASELINE],
            ),
            (AMENDED_PLAN_COMMIT, PLAN_COMMIT),
        )

        mocks = self._run_handoff_tick(
            gh,
            crashed,
            run_agent=_agent(interrupted=True),
            branch_tip_sha=AMENDED_PLAN_COMMIT,
            has_new_commits=True,
            head_shas=(AMENDED_PLAN_COMMIT,) * 3,
        )

        # The developer runs on their head rather than the shortcut publishing
        # it, and the move the crash interrupted is finished and spent.
        self._assert_dev_ran(mocks)
        mocks[PUSH_BRANCH].assert_not_called()
        pinned_data = gh.pinned_data(crashed.number)
        self.assertEqual(
            (
                pinned_data[KEY_PLAN_SHA],
                pinned_data[KEY_READ_ONLY_BASELINE],
                pinned_data[KEY_HANDOFF_ANCHOR],
            ),
            (AMENDED_PLAN_COMMIT, AMENDED_PLAN_COMMIT, None),
        )

    def _assert_merged_plan_builds(self, issue_number: int, head_sha: str):
        """A landed design starts a developer at the base, not at `done`."""
        gh, merged = _seed_accepted_handoff(issue_number, head_sha=head_sha)

        mocks = self._interrupted_tick(gh, merged)

        self.assertNotIn((merged.number, LABEL_DONE), gh.label_history)
        self._assert_dev_ran(mocks)
        self.assertEqual(
            mocks[ANCHOR_PR_WORKTREE].call_args.kwargs[_HEAD_ARG],
            _ONTO_THE_BASE,
        )
        self.assertEqual(
            gh.pinned_data(merged.number)[KEY_READ_ONLY_BASELINE],
            BASE_TIP_SHA,
        )

    def _interrupted_tick(self, gh, issue):
        """One tick whose dev run is killed, leaving only durable writes."""
        return self._run_handoff_tick(
            gh, issue, run_agent=_agent(interrupted=True),
        )


if __name__ == "__main__":
    unittest.main()
