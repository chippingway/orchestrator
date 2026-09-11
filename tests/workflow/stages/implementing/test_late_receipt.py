# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the publication receipt vouches for, and what it may not.

`implementing_published_sha` is the note this stage leaves naming the commit it
pushed, and the window it exists for is the one between that push and a relabel
that never landed: the branch is on the remote, a pull request carries it, and
the record still says implementing. A tick reading that as fresh work would
measure a published commit and, finding it oversized, route it into an
adjudication with nothing left to hold back.

That is the receipt answering ALONE, and it is right for a commit this gate
measured on the way out. It is not right for one an exemption names and nothing
authorizes. The note is never cleared, so a branch that has been on the remote
before arrives carrying one -- and where the remote has since moved off that
commit, or the pull request is gone entirely, answering on the note alone
republishes unmeasured bulk with no frozen head to lease the push against.
There is nothing at this seam that could prove the pull request still carries
it: proving that is what a frozen publication IS, and the implementing side has
none.

So the receipt is refused there and the candidate goes to the ordinary
cumulative reading, which parks an oversized one for the authorization it is
missing.
"""

from __future__ import annotations

import unittest
from types import MappingProxyType
from unittest.mock import patch

from orchestrator.workflow.stages.implementing import (
    late_overflow as _overflow,
)
from tests.support.fakes import FakePR, FakePRRef
from tests.workflow.fixtures import (
    LABEL_VALIDATING,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
    _authorized_exemption,
    _issue_branch,
)
from tests.workflow.interleaving import _RacesTheStep
from tests.workflow.stages.implementing import (
    late_authority_test_support as legacy,
    late_gate_test_support as support,
)

_KEY_PUBLISHED_SHA = "implementing_published_sha"

# The pull request that note was written about, and the branch it is on.
_PR_NUMBER = 812
_BRANCH = _issue_branch(support.GATE_ISSUE_NUMBER)

# Where the remote is standing instead: a commit of the right shape that no
# record on these seeds names, which is what "the head has moved" looks like
# from the issue's side.
_MOVED_HEAD = "e" * SHA_LENGTH

_VALIDATING = (support.GATE_ISSUE_NUMBER, LABEL_VALIDATING)

# The two keywords a gated push names its commit and pins its ref by, and the
# reading the bookkeeping behind the proof resolves its pull request through.
_REVISION = "revision"
_LEASE = "force_with_lease"
_STILL_OPEN = "still_open"

# What a pull request reads as once somebody has ended it.
_CLOSED = "closed"

# The branch a pull request nobody opened for this issue is on: the shape a
# record whose `branch` and `pr_number` disagree leaves, and the one that
# would have the seam push somewhere nothing has published.
_ANOTHER_BRANCH = f"{_BRANCH}-elsewhere"

# What a branch this stage has pushed before carries: the note naming the
# commit it sent, the pull request that push opened, and the branch both are
# about. All three, because the remote reading behind them is what tells
# adjudicated work this issue delivered from a tip somebody else moved the
# branch to -- and because the seam behind the answer resolves its own branch
# from this record and reuses whatever open pull request is on it.
_PUBLISHED_BY_THIS_STAGE = MappingProxyType({
    _KEY_PUBLISHED_SHA: MEASURED_CANDIDATE_SHA,
    "pr_number": _PR_NUMBER,
    "branch": _BRANCH,
})


class _ReceiptCase(legacy._LegacyExemptionCase):
    """An issue whose branch this stage has pushed before."""

    def _receipt_for_a_legacy_exemption(self) -> None:
        """The note an older binary's automatic exemption left on its push."""
        self._seed_legacy(**_PUBLISHED_BY_THIS_STAGE)

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


class DeliveredReceiptTest(_ReceiptCase, unittest.TestCase):
    """Adjudicated work the pull request this stage opened already carries."""

    def test_a_delivered_receipt_finishes_up(self) -> None:
        # The window this seam's own receipt exists for, read from the far
        # end: this stage pushed the commit, the pull request it opened is
        # standing on it still, and the relabel never landed. The push would
        # move nothing, so what a hold would hold back is the bookkeeping
        # behind a publication that has already happened -- which leaves
        # published work under a stage no later tick advances.
        self._stand_the_pull_request_on(MEASURED_CANDIDATE_SHA)
        self._receipt_for_a_legacy_exemption()

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_unmeasured(mocks)
        self.assertIn(_VALIDATING, self.github.label_history)

    def test_it_publishes_nothing_a_second_time(self) -> None:
        # What "finishing the bookkeeping" has to mean, and the whole of why
        # the reading is held to the branch as well as the tip: the seam
        # behind this answer pushes the branch IT resolves and reuses the open
        # pull request on it. Named the same, the push has nothing to send and
        # the lookup finds the very pull request the reading proved; named
        # differently, the same road would publish to a branch nobody has
        # pushed and open a second pull request over the same work.
        self._stand_the_pull_request_on(MEASURED_CANDIDATE_SHA)
        self._receipt_for_a_legacy_exemption()

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self.assertEqual(
            mocks[support.PUSH_BRANCH].call_args.args[2], _BRANCH,
        )
        self.assertEqual(self.github.opened_prs, [])
        self.assertEqual(
            self._pinned()["pr_number"], _PR_NUMBER,
        )

    def test_a_pull_request_elsewhere_is_measured(self) -> None:
        # The record disagreeing with itself: the pull request it names is
        # open on a branch this seam would not push, so nothing here can say
        # the work has been delivered where the push would land. Waved
        # through, the push would go to the branch the record resolves and a
        # SECOND pull request would be opened over the same commit.
        self._stand_the_pull_request_on(
            MEASURED_CANDIDATE_SHA, branch=_ANOTHER_BRANCH,
        )
        self._receipt_for_a_legacy_exemption()

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_held(mocks)

    def test_a_tip_no_receipt_names_is_measured(self) -> None:
        # Both halves are required and neither is widened. A head the remote
        # happens to agree with says nothing about how it got there, so
        # without the receipt beside it a legacy exemption would publish
        # unmeasured over any branch somebody else pushed the commit to.
        self._stand_the_pull_request_on(MEASURED_CANDIDATE_SHA)
        self._seed_legacy(pr_number=_PR_NUMBER)

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_held(mocks)


class UnauthorizedReceiptTest(_ReceiptCase, unittest.TestCase):
    """A receipt standing beside an exemption nobody authorized."""

    def test_a_stale_receipt_is_measured(self) -> None:
        # Both endings of the same publication: a pull request a human pushed
        # over, and one somebody deleted. Neither still carries the commit the
        # note names, so the local note is all that is left -- and it is never
        # cleared, so answering on it would republish an oversized change
        # nobody measured onto a branch the remote has moved off.
        for described, standing in (
            ("moved off it", _MOVED_HEAD),
            ("gone from under it", ""),
        ):
            with self.subTest(pull_request=described):
                self.setUp()
                self._stand_the_pull_request_on(standing)
                self._receipt_for_a_legacy_exemption()

                mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

                self._assert_measured(mocks)
                self._assert_held(mocks)

    def test_a_refused_receipt_parks(self) -> None:
        # Where the reading then puts it: parked on the one refusal a named
        # command answers, rather than routed back into an adjudication that
        # has already ruled this change one change. The record it was refused
        # on is still there, so the authorization has something to name.
        self._stand_the_pull_request_on(_MOVED_HEAD)
        self._receipt_for_a_legacy_exemption()

        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_waiting_for_authorization()
        self._assert_kept_the_record()

    def test_an_authorized_receipt_publishes(self) -> None:
        # The other side of the rule, so the refusals above are about the
        # missing half rather than about the receipt having stopped working:
        # the pair a human authorized publishes without a reading whatever the
        # remote is standing on.
        self._stand_the_pull_request_on(_MOVED_HEAD)
        self._seed(**{
            **_authorized_exemption(),
            **_PUBLISHED_BY_THIS_STAGE,
        })

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_unmeasured(mocks)
        self._assert_published(mocks)

class DeliveredWindowTest(_ReceiptCase, unittest.TestCase):
    """What moves between the proof and the push, and what the proof pins.

    The reading that admits an already-delivered candidate is a request, and
    everything after it is another: the branch is somebody else's to move and
    the pull request somebody else's to close. So the answer carries both of
    the things the seam behind it would otherwise resolve for itself -- the
    lease, which is that commit, and the pull request the bookkeeping belongs
    to -- and each is pinned to what the proof was actually about.
    """

    def setUp(self) -> None:
        super().setUp()
        self._stand_the_pull_request_on(MEASURED_CANDIDATE_SHA)
        self._receipt_for_a_legacy_exemption()

    def test_the_push_is_leased_to_that_commit(self) -> None:
        # Left to the transport's own reading, a tip somebody moved in the
        # window is adopted AS the lease and the candidate is force-pushed
        # over it. Pinned to the commit the proof was about, the same push
        # sends nothing where the branch has not moved and is refused where
        # it has.
        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        pushed = mocks[support.PUSH_BRANCH].call_args
        self.assertEqual(pushed.kwargs[_LEASE], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.kwargs[_REVISION], MEASURED_CANDIDATE_SHA)

    def test_a_pull_request_closing_opens_none(self) -> None:
        # The other half of the same window. Looked up by branch a moment
        # later, a pull request somebody closed answers None and the seam
        # opens a SECOND one over work the first already carries. Pinned to
        # the number the proof named, the same window holds the tick instead
        # and leaves the record exactly as it stands.
        with patch.object(
            _overflow._PublicationReading,
            _STILL_OPEN,
            _RacesTheStep(
                _overflow._PublicationReading.still_open, self._closes_it,
            ),
        ):
            mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_unmeasured(mocks)
        self.assertEqual(self.github.opened_prs, [])
        self.assertNotIn(_VALIDATING, self.github.label_history)

    def _closes_it(self) -> None:
        """Close the pull request the proof named, as another poll would."""
        self.github.get_pr(_PR_NUMBER).state = _CLOSED


class VouchedReceiptTest(_ReceiptCase, unittest.TestCase):
    """What a receipt is evidence of, and what it takes to be evidence at all.

    The window this note exists for is real and the refusal beside it may not
    close it: nothing says the commit was ever exempt, so it went out through
    a reading and the only thing missing is the relabel. Read as fresh work it
    would be measured, and an oversized answer there routes published work
    into an adjudication with nothing left to hold back.

    But the note says only what this stage last PUSHED -- never where it went
    or whether it is still there -- so the window it covers has to be proved
    rather than assumed, on exactly the terms the delivered exemption's is.
    """

    def test_a_measured_receipt_still_answers(self) -> None:
        self._stand_the_pull_request_on(MEASURED_CANDIDATE_SHA)
        self._seed(**_PUBLISHED_BY_THIS_STAGE)

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_unmeasured(mocks)
        self.assertIn(_VALIDATING, self.github.label_history)
        self.assertEqual(self.github.opened_prs, [])

    def test_a_receipt_with_no_pr_is_measured(self) -> None:
        # The reproduction this proof exists for: a note naming a commit and a
        # record naming no pull request, or one this host cannot read. Trusted
        # on its own, the candidate skips the reading, is pushed, opens a
        # SECOND pull request, and the issue is handed on as though the work
        # had been published all along.
        for described, recorded in (
            ("no pull request at all", {_KEY_PUBLISHED_SHA: MEASURED_CANDIDATE_SHA}),
            ("one this host cannot read", dict(_PUBLISHED_BY_THIS_STAGE)),
        ):
            with self.subTest(record=described):
                self.setUp()
                self._seed(**recorded)

                mocks = self._run_gate(
                    added_lines=support.OVERSIZED_ADDITIONS,
                )

                self._assert_measured(mocks)
                self._assert_held(mocks)
                self.assertEqual(self.github.opened_prs, [])

    def test_a_receipt_over_a_moved_branch_fails(self) -> None:
        # And the same where the pull request is there and has moved on: the
        # note is never cleared, so on its own it would republish work the
        # branch no longer carries onto a head nothing leased.
        self._stand_the_pull_request_on(_MOVED_HEAD)
        self._seed(**_PUBLISHED_BY_THIS_STAGE)

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_held(mocks)

if __name__ == "__main__":
    unittest.main()
