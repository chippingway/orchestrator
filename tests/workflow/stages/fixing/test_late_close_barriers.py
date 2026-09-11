# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Every barrier between a close and a push onto a pull request nobody wants.

The reconciliation that runs ahead of every stage ends in a PUSH -- the
reading it takes does, and the debt road beside it exists to make one -- while
the terminal that drains a closed issue runs inside the stage handler behind
both. So a close reaching the orchestrator between the crash and the recovery
is the way work would otherwise land on a pull request nobody wants.

Two facts answer it, and they are answered differently. The issue OBJECT is
the snapshot the tick opened with, and a close it already carries is answered
at the reconciliation's door by handing the tick back -- the handler's own
terminal is next, and it drains the issue with the record, the branch and the
debt left exactly as they are. Everything the tick spends after that door -- a
stage check, a checkout probe, a remote read, a diff -- is time a poll on
another worker can find the issue closed in, and only the process-wide latch
can say so. That one STOPS the tick instead: the object still reads open, so
the terminal would find nothing to finalize and the handler would spawn an
agent on an issue somebody closed.

The last of them is inside the publication, immediately before the push and
nowhere else in it: every guard above that line spends a reading, a diff or a
request after it, and a close landing in one of those windows would be
answered one push too late.
"""

from __future__ import annotations

import unittest
from types import MappingProxyType

from tests.support.fakes import FakeGitHubClient, FakePRRef, make_issue
from tests.workflow.fixtures import (
    _TEST_SPEC,
    MEASURED_CANDIDATE_SHA,
    _authorized_exemption,
    _issue_branch,
    _open_pr_for,
)
from tests.workflow.observation_support import ObservedCloseCase
from tests.workflow.stages.fixing import (
    fixing_test_support as fixing,
    published_gate_support as support,
)
from tests.workflow.stages.fixing.test_late_dispatch import (
    ISSUE,
    PR_NUMBER,
    PUSH_BRANCH,
    _FrozenPairMixin,
)

_REPO_SLUG = _TEST_SPEC.slug

# The debt a tick that died between the retirement and the push leaves: one
# commit owed a publication, and the head the pull request was standing on
# when it was approved. No generation beside it, which is what makes this the
# window the frozen pair cannot cover.
_OWED_PUBLICATION = MappingProxyType({
    support.KEY_APPROVED_SHA: MEASURED_CANDIDATE_SHA,
    support.KEY_APPROVED_LEASE: fixing.PR_HEAD_SHA,
})


def _owing(case):
    """An issue whose only late record is a push an approval still owes.

    Seeded rather than reached through the frozen pair beside it, because the
    two are different windows: this one opens past the write that retired the
    generation, so there is no record left for the reading to be re-entered
    from and the approval is the whole of what says a push is owed.
    """
    github = FakeGitHubClient()
    issue = make_issue(ISSUE, label=fixing.FIXING)
    github.add_issue(issue)
    github.seed_state(
        ISSUE,
        branch=_issue_branch(ISSUE),
        pr_number=PR_NUMBER,
        **_OWED_PUBLICATION,
    )
    _open_pr_for(
        github,
        issue_number=ISSUE,
        pr_number=PR_NUMBER,
        head=FakePRRef(sha=fixing.PR_HEAD_SHA),
    )
    return github, issue


# The two records this owner goes back for, which are the two windows a crash
# between the gate and the push can leave.
_RECOVERABLE = MappingProxyType({
    "a frozen pair": lambda case: case._frozen(),
    "a debt a crash left": _owing,
})


class ClosedIssueReconciliationTest(
    ObservedCloseCase, unittest.TestCase, _FrozenPairMixin,
):
    """A close the tick's own snapshot already carries, answered at the door."""

    def setUp(self) -> None:
        self._fresh_process()

    def test_a_closed_issue_publishes_nothing(self) -> None:
        # Both roads out of this owner publish, and both are behind the door.
        # A frozen pair is measured and pushed; a debt is paid by a push of
        # its own. Neither may happen on an issue somebody closed.
        for described, owed in _RECOVERABLE.items():
            with self.subTest(record=described):
                github = self._closed(owed)

                mocks = self._route(github, github.get_issue(ISSUE))[1]

                mocks[PUSH_BRANCH].assert_not_called()

    def test_the_debt_is_handed_to_the_terminal(self) -> None:
        # Handing the tick back costs nothing here, and it is the whole reason
        # the door reads the object: the stage's own terminal is the next
        # thing that runs, and it drains the issue with the record, the branch
        # and the debt left exactly as they are for it.
        github = self._closed(_owing)

        dispatched = self._route(github, github.get_issue(ISSUE))[0]

        dispatched.assert_called_once()
        self.assertEqual(
            github.pinned_data(ISSUE)[support.KEY_APPROVED_SHA],
            MEASURED_CANDIDATE_SHA,
        )

    def _closed(self, owed):
        """That record, on an issue whose own object already says closed."""
        github = owed(self)[0]
        github.add_issue(make_issue(ISSUE, label=fixing.FIXING, closed=True))
        return github


class LatchedCloseReconciliationTest(
    ObservedCloseCase, unittest.TestCase, _FrozenPairMixin,
):
    """A close a later poll saw, answered against the latch instead."""

    def setUp(self) -> None:
        self._fresh_process()
        self._latch_close(_REPO_SLUG, ISSUE)

    def test_a_latched_close_stops_the_tick(self) -> None:
        # The object this tick holds still reads open, so handing the tick
        # back would reach a terminal with nothing to finalize and a handler
        # that spawns an agent. What advances the issue instead is the cleanup
        # pass every latched close is owed.
        for described, owed in _RECOVERABLE.items():
            with self.subTest(record=described):
                dispatched, mocks = self._route(*owed(self))

                mocks[PUSH_BRANCH].assert_not_called()
                dispatched.assert_not_called()

    def test_the_record_is_left_for_the_cleanup(self) -> None:
        # Nothing is relabelled, announced or dropped: the debt and the pair
        # the recovery would have spent are what the cleanup pass reads.
        github, issue = _owing(self)

        self._route(github, issue)

        pinned = github.pinned_data(ISSUE)
        self.assertEqual(
            pinned[support.KEY_APPROVED_SHA], MEASURED_CANDIDATE_SHA,
        )
        self.assertEqual(github.label_history, [])


class LatchedClosePublicationTest(
    ObservedCloseCase, unittest.TestCase, support._SizeGateFixtureMixin,
):
    """The last barrier of all, immediately before the push itself.

    Reached on a candidate that skips the reading, because that is the road
    with no record to retire: a measured one is ended by the cancellation
    inside the retirement, and only a publication with nothing to retire gets
    this far with a close latched against it.
    """

    def setUp(self) -> None:
        self._fresh_process()
        self.scenario = self._seed_fix_round(**_authorized_exemption())
        self._latch_close(_REPO_SLUG, fixing.ISSUE)

    def test_a_latched_close_refuses_the_push(self) -> None:
        # What a closed issue may never earn is exactly this effect, so the
        # refusal is held: nothing pushed, nothing relabelled, nothing
        # announced, and the record left for the cleanup a latched close owes.
        mocks = self._run_fix_round(self.scenario)

        self._assert_unpushed(mocks)
        self.assertEqual(self.scenario.github.label_history, [])


if __name__ == "__main__":
    unittest.main()
