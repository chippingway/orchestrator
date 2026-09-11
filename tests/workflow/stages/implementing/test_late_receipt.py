# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the publication receipt vouches for, and what it may not.

`implementing_published_sha` is the note this stage leaves naming the commit it
pushed, and the window it exists for is the one between that push and a relabel
that never landed: the branch is on the remote, a pull request carries it, and
the record still says implementing. A tick reading that as fresh work would
measure a published commit and, finding it oversized, route it into an
adjudication with nothing left to hold back.

That window is real and nothing here closes it. What is proved is that the tick
is still IN it: the note says what this stage last pushed and nothing about
where it went or whether it is still there, and it is never cleared -- so a
branch published rounds ago carries one for the rest of the issue's life.
Answered on the note alone, the candidate skips the reading, is pushed
unmeasured and unleased, opens a SECOND pull request over work the first
already carries, and the issue is handed on as though all of it had been
published all along.

So the same proof stands behind every road that rests on it: the pull request
the record names, open, on the branch this seam would push, standing on this
exact commit. And because a reading is a moment, what the answer carries is the
NUMBER -- the push behind it is leased against that commit, and the bookkeeping
is bound to that pull request.
"""

from __future__ import annotations

import unittest
from types import MappingProxyType
from unittest.mock import patch

from orchestrator.workflow.stages.implementing import (
    late_overflow as _overflow,
    publication as _publication,
)
from tests.support.fakes import FakePR, FakePRRef
from tests.workflow.fixtures import (
    LABEL_VALIDATING,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
    _issue_branch,
)
from tests.workflow.interleaving import _RacesPastTheStep, _RacesTheStep
from tests.workflow.stages.implementing import late_gate_test_support as support

_KEY_PUBLISHED_SHA = "implementing_published_sha"
_KEY_PR_NUMBER = "pr_number"

# The pull request that note was written about, and the branch it is on.
_PR_NUMBER = 812
_BRANCH = _issue_branch(support.GATE_ISSUE_NUMBER)

# Where the remote is standing instead: a commit of the right shape that no
# record on these seeds names, which is what "the head has moved" looks like
# from the issue's side.
_MOVED_HEAD = "e" * SHA_LENGTH

# The branch a pull request nobody opened for this issue is on: the shape a
# record whose `branch` and `pr_number` disagree leaves, and the one that
# would have the seam push where nothing has published.
_ANOTHER_BRANCH = f"{_BRANCH}-elsewhere"

_VALIDATING = (support.GATE_ISSUE_NUMBER, LABEL_VALIDATING)

# The two keywords a push names its commit and pins its ref by, and the
# reading the bookkeeping behind the proof resolves its pull request through.
_REVISION = "revision"
_LEASE = "force_with_lease"
_STILL_OPEN = "still_open"

# The last step this seam takes before its barrier, which is the window a poll
# on another worker can end the publication in.
_PUBLICATION_INTENT = "_publication_intent"

# What a pull request reads as once somebody has ended it.
_CLOSED = "closed"

# A receipt outside this domain's object-id vocabulary: what a hand edit or a
# half-written crash leaves, and what every late commit field reads back as an
# absence rather than as the claim it is.
_MALFORMED_RECEIPT = "not-a-sha"

# What a branch this stage has pushed before carries: the note naming the
# commit it sent, the pull request that push opened, and the branch both are
# about. All three, because the remote reading behind them is what tells work
# this issue delivered from a tip somebody else moved the branch to.
_PUBLISHED_BY_THIS_STAGE = MappingProxyType({
    _KEY_PUBLISHED_SHA: MEASURED_CANDIDATE_SHA,
    _KEY_PR_NUMBER: _PR_NUMBER,
    "branch": _BRANCH,
})


class _ReceiptCase(support._GateCase):
    """An issue whose branch this stage has pushed before."""

    def _stand_the_pull_request_on(
        self, head: str, branch: str = _BRANCH,
    ) -> None:
        """Put this issue's open pull request on `head`, or take it away.

        `branch` is what the pull request's own head names, which a case about
        a record disagreeing with itself moves off the branch the seam would
        push -- the one shape that would have the answer license a push onto a
        branch nothing has published.
        """
        if not head:
            return
        opened = FakePR(
            number=_PR_NUMBER,
            head_branch=branch,
            head=FakePRRef(sha=head, ref=branch),
        )
        self.github.add_pr(opened)
        self.github.existing_open_pr[branch] = opened

    def _oversized(self):
        """One gate run over a candidate no count would ever let through."""
        return self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)


class DeliveredReceiptTest(_ReceiptCase, unittest.TestCase):
    """The window the note exists for, proved rather than assumed."""

    def setUp(self) -> None:
        super().setUp()
        self._stand_the_pull_request_on(MEASURED_CANDIDATE_SHA)
        self._seed(**_PUBLISHED_BY_THIS_STAGE)

    def test_a_proved_receipt_finishes_up(self) -> None:
        # Read from the far end: this stage pushed the commit, the pull
        # request it opened is standing on it still, and the relabel never
        # landed. Nothing is measured, nothing new is opened, and the issue
        # is handed on -- which is what a hold here would strand.
        mocks = self._oversized()

        self._assert_unmeasured(mocks)
        self.assertIn(_VALIDATING, self.github.label_history)
        self.assertEqual(self.github.opened_prs, [])
        self.assertEqual(self._pinned()[_KEY_PR_NUMBER], _PR_NUMBER)

    def test_the_push_is_leased_to_that_commit(self) -> None:
        # Left to the transport's own reading, a tip somebody moved in the
        # window is adopted AS the lease and the candidate is force-pushed
        # over it. Pinned to the commit the proof was about, the same push
        # sends nothing where the branch has not moved and is refused where
        # it has.
        pushed = self._oversized()[support.PUSH_BRANCH].call_args

        self.assertEqual(pushed.kwargs[_LEASE], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.kwargs[_REVISION], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.args[2], _BRANCH)

    def test_one_closing_before_the_push_sends_none(self) -> None:
        # The barrier the push itself owes, raced into the window it exists
        # for: the gate proved the pull request open, and a poll on another
        # worker closes it before the transport runs. The lease makes no
        # difference there -- a branch nobody moved accepts the push whatever
        # became of the pull request over it -- so the reading is retaken
        # immediately before the push rather than only at the bookkeeping
        # behind it.
        with patch.object(
            _publication,
            _PUBLICATION_INTENT,
            _RacesPastTheStep(
                _publication._publication_intent, self._closes_it,
            ),
        ):
            mocks = self._oversized()

        self._assert_held(mocks)
        self.assertEqual(self.github.opened_prs, [])
        self.assertNotIn(_VALIDATING, self.github.label_history)

    def test_a_pull_request_closing_opens_none(self) -> None:
        # The far end of the same window. Looked up by branch a moment later,
        # a pull request somebody closed answers None and the seam opens a
        # SECOND one over work the first already carries. Pinned to the number
        # the proof named, the same window holds the tick instead and leaves
        # the record exactly as it stands.
        with patch.object(
            _overflow._PublicationReading,
            _STILL_OPEN,
            _RacesTheStep(
                _overflow._PublicationReading.still_open, self._closes_it,
            ),
        ):
            mocks = self._oversized()

        self._assert_unmeasured(mocks)
        self.assertEqual(self.github.opened_prs, [])
        self.assertNotIn(_VALIDATING, self.github.label_history)

    def _closes_it(self) -> None:
        """Close the pull request the proof named, as another poll would."""
        self.github.get_pr(_PR_NUMBER).state = _CLOSED


# Every way the publication a receipt names can fail to be shown, each named
# by what the pinned comment and the remote disagree about.
_UNPROVABLE = MappingProxyType({
    "no pull request at all": ("", _BRANCH, {}),
    "one this host cannot read": ("", _BRANCH, _PUBLISHED_BY_THIS_STAGE),
    "one the branch moved off": (
        _MOVED_HEAD, _BRANCH, _PUBLISHED_BY_THIS_STAGE,
    ),
    "one open somewhere else": (
        MEASURED_CANDIDATE_SHA, _ANOTHER_BRANCH, _PUBLISHED_BY_THIS_STAGE,
    ),
    "one somebody ended": (
        MEASURED_CANDIDATE_SHA, _BRANCH, _PUBLISHED_BY_THIS_STAGE,
    ),
    "a receipt nothing can read": (
        MEASURED_CANDIDATE_SHA, _BRANCH,
        {**_PUBLISHED_BY_THIS_STAGE, _KEY_PUBLISHED_SHA: _MALFORMED_RECEIPT},
    ),
})


class UnprovableReceiptTest(_ReceiptCase, unittest.TestCase):
    """Every record the note stands beside that proves nothing at all.

    Held fail-CLOSED rather than measured, and the size of the candidate is
    exactly why. Falling through to the reading is not a neutral answer: a
    count under the ceiling PUBLISHES, which force-pushes a branch nothing
    here could confirm and opens a second pull request over work the first may
    already carry -- the outcome the whole proof exists to close, reached by
    the commonest reading there is.
    """

    def test_an_unprovable_receipt_is_held(self) -> None:
        # Each half of the proof, missing on its own, against a candidate the
        # ceiling would wave straight through. No pull request recorded at
        # all, one this host cannot read, one the branch has moved off, one
        # open where this seam would never push, and one somebody closed.
        for described in _UNPROVABLE:
            with self.subTest(record=described):
                self._seeded(described)

                mocks = self._run_gate(added_lines=support.SMALL_ADDITIONS)

                self._assert_unmeasured(mocks)
                self._assert_held(mocks)

    def test_the_record_is_left_for_the_retry(self) -> None:
        # What the park may not cost: the receipt, the pull request it names,
        # and the commit itself are what a terminal drains and what a repaired
        # record republishes from, so the refusal writes the park and nothing
        # else.
        self._seeded("one the branch moved off")

        self._run_gate(added_lines=support.SMALL_ADDITIONS)

        pinned = self._pinned()
        self.assertTrue(pinned[support.AWAITING_HUMAN])
        self.assertEqual(
            pinned[support.PARK_REASON], support.PARK_MEASUREMENT_FAILED,
        )
        self.assertEqual(pinned[_KEY_PUBLISHED_SHA], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pinned[_KEY_PR_NUMBER], _PR_NUMBER)

    def test_an_oversized_one_is_held_the_same_way(self) -> None:
        # The same answer on the road that would have been held anyway, so the
        # refusal reads as one rule rather than as a size question.
        self._seeded("one open somewhere else")

        mocks = self._oversized()

        self._assert_unmeasured(mocks)
        self._assert_held(mocks)

    def test_a_malformed_receipt_is_kept(self) -> None:
        # The shape the comparison below it cannot see: read fail-closed the
        # note comes back as no receipt at all, so the candidate is measured,
        # published, and the damaged field overwritten by the receipt that
        # push writes -- which destroys the one record an operator could have
        # repaired it from. It says this stage pushed and cannot say what, so
        # nothing here can tell whether the commit in hand is that commit.
        self._seeded("a receipt nothing can read")

        mocks = self._run_gate(added_lines=support.SMALL_ADDITIONS)

        self._assert_unmeasured(mocks)
        self._assert_held(mocks)
        self.assertEqual(
            self._pinned()[_KEY_PUBLISHED_SHA], _MALFORMED_RECEIPT,
        )

    def test_a_tip_no_receipt_names_is_measured(self) -> None:
        # The other half, and it is not widened either: a head the remote
        # happens to agree with says nothing about how it got there, so
        # without the note beside it any branch somebody else pushed the
        # commit to would wave the candidate past. Nothing here claims a
        # publication, so nothing is held back either.
        self._stand_the_pull_request_on(MEASURED_CANDIDATE_SHA)
        self._seed(pr_number=_PR_NUMBER, branch=_BRANCH)

        mocks = self._oversized()

        self._assert_measured(mocks)
        self._assert_held(mocks)

    def _seeded(self, described: str) -> None:
        """One record whose receipt names a publication nothing can show."""
        standing, branch, recorded = _UNPROVABLE[described]
        self.setUp()
        self._stand_the_pull_request_on(standing, branch=branch)
        if described == "one somebody ended":
            self.github.get_pr(_PR_NUMBER).state = _CLOSED
        self._seed(**{
            _KEY_PUBLISHED_SHA: MEASURED_CANDIDATE_SHA, **recorded,
        })


if __name__ == "__main__":
    unittest.main()
