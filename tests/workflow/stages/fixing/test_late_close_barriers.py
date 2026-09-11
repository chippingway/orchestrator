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
from functools import partial
from types import MappingProxyType
from unittest.mock import patch

from orchestrator.workflow.stages.implementing import late_push as _late_push
from tests.support.fakes import FakeGitHubClient, FakePRRef, make_issue
from tests.workflow.fixtures import (
    _TEST_SPEC,
    MEASURED_CANDIDATE_SHA,
    _authorized_exemption,
    _issue_branch,
    _open_pr_for,
)
from tests.workflow.interleaving import _RacesPastTheStep
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

# What a pull request reads as once it is over, whichever way it ended.
_CLOSED = "closed"

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


def _ended(github, *, merged: bool = False) -> None:
    """End this issue's pull request, which leaves the ISSUE itself open.

    A merge and a plain close are one shape with one flag between them, and
    the flag matters: the two are different endings to a reader, and a fixture
    spelling only one of them would leave the commoner of the two untested.
    """
    pull_request = github.get_pr(PR_NUMBER)
    pull_request.merged = merged
    pull_request.state = _CLOSED


def _unreadable(github) -> None:
    """Take the pull request off this host's reading entirely."""
    github.pulls.pop(PR_NUMBER, None)


# The two endings a pull request has, plus the reading that cannot say which:
# every state a push immediately behind it may not land on.
_ENDINGS = MappingProxyType({
    "merged": partial(_ended, merged=True),
    "closed": _ended,
    "unreadable": _unreadable,
})

# The step the gated publication takes last before its barrier, which is the
# window a pull request can end in without the gate above ever seeing it.
_REPINNED = "_repinned"


# Each ending against both records the reconciliation goes back for: polls
# that have nowhere to push and one answer.
_TERMINAL_ROADS = MappingProxyType({
    f"{ending} over {described}": (_ENDINGS[ending], owed)
    for ending in ("merged", "closed")
    for described, owed in (
        ("a frozen pair", _RECOVERABLE["a frozen pair"]),
        ("a debt a crash left", _owing),
    )
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


class TerminalPullRequestTest(
    ObservedCloseCase, unittest.TestCase, _FrozenPairMixin,
):
    """A pull request that is over, on an issue nobody has closed yet.

    The other terminal state, and the one the closed-issue guard cannot see.
    A merge leaves the ISSUE open until the stage terminal behind this owner
    reads it and finalizes the work, and everything this owner does in between
    ends in a push onto exactly that pull request -- which the gate refuses to
    freeze an entry against, so the road below would park the issue for a
    human over a publication that is finished.
    """

    def setUp(self) -> None:
        self._fresh_process()

    def test_a_terminal_pull_request_is_handed_on(self) -> None:
        # Both endings, and both roads out of this owner. Neither has anywhere
        # for a push to land, and a `late_measurement_failed` park is the
        # wrong answer to either: what such an issue is owed is the terminal.
        for ending, record in _TERMINAL_ROADS.items():
            with self.subTest(case=ending):
                self.assertIsNone(self._reconciled(*record))

    def test_an_open_one_is_still_reconciled(self) -> None:
        # The other side, so the guard is about the ending rather than about
        # pull requests: the same record over a pull request the work can
        # still join is measured and published before the stage runs.
        dispatched, mocks = self._route(*self._frozen())

        mocks[PUSH_BRANCH].assert_called_once()
        dispatched.assert_called_once()

    def _reconciled(self, over, owed) -> None:
        """Run one poll over that record, and assert what it left behind."""
        github, issue = owed(self)
        over(github)
        dispatched, mocks = self._route(github, issue)
        mocks[PUSH_BRANCH].assert_not_called()
        dispatched.assert_called_once()
        self.assertIsNone(
            github.pinned_data(ISSUE).get(fixing.PARK_REASON),
        )


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


class EndedBeforeThePushTest(
    ObservedCloseCase, unittest.TestCase, support._SizeGateFixtureMixin,
):
    """The last barrier of all, immediately before the push itself.

    Reached on a candidate that skips the reading, because that is the road
    with no record to retire: a measured one is ended by the cancellation
    inside the retirement, and only a publication with nothing to retire gets
    this far with the world having ended under it.

    Two things can have ended, and the pull request is the one nothing above
    catches. The gate refuses to ENTER a call on one that is already over, so
    the only way one reaches the push is by ending in the window behind that
    reading -- the freeze, the whole gated measurement, and the repin. Its
    branch is still at the head this tick froze there, so the lease SUCCEEDS:
    the force-push lands and moves a merged pull request's branch back onto
    the commits it merged, which is the one effect nothing can undo.
    """

    def setUp(self) -> None:
        self._fresh_process()
        self.scenario = self._seed_fix_round(**_authorized_exemption())

    def test_a_latched_close_refuses_the_push(self) -> None:
        # What a closed issue may never earn is exactly this effect, so the
        # refusal is held: nothing pushed, nothing relabelled, nothing
        # announced, and the record left for the cleanup a latched close owes.
        self._latch_close(_REPO_SLUG, fixing.ISSUE)

        self._assert_refused(self._run_fix_round(self.scenario))

    def test_an_ending_pull_request_refuses_it(self) -> None:
        # Every state a push may not land on, raced into the window the
        # barrier exists for -- the unreadable one included, since this
        # reading fails CLOSED where the same one at the reconciliation's door
        # falls through: there it costs a poll, and here a branch whose pull
        # request may already be merged.
        for ending, over in _ENDINGS.items():
            with self.subTest(pull_request=ending):
                self.setUp()

                self._assert_refused(self._raced(over))

    def test_one_still_open_publishes_as_ever(self) -> None:
        # The other side, so the barrier is about the ending rather than
        # about spending a request: nothing raced, and the push lands.
        self._assert_pushed_once(self._run_fix_round(self.scenario))

    def _assert_refused(self, mocks) -> None:
        """Nothing pushed, and nothing handed on behind it."""
        self._assert_unpushed(mocks)
        self.assertEqual(self.scenario.github.label_history, [])

    def _raced(self, ending):
        """Run one fix round, ending the pull request just past the repin.

        Hung on the repin because that is the last step before the barrier:
        the gate has read the pull request by then and the push has not run,
        which is exactly the window a poll on another worker can end it in.
        """
        with patch.object(
            _late_push,
            _REPINNED,
            _RacesPastTheStep(
                _late_push._repinned,
                lambda: ending(self.scenario.github),
            ),
        ):
            return self._run_fix_round(self.scenario)


if __name__ == "__main__":
    unittest.main()
