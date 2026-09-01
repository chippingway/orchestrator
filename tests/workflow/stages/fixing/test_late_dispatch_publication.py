# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the reconciliation publishes before it lets a stage run.

Two shapes of unfinished publication reach the tick ahead of every handler,
and both end the same way: the pull request carries the commit before the
stage that would work from it runs.

A frozen PAIR is a reading the crash interrupted. Answered for its verdict
alone, the record retires naming a commit still owed a push and the handler
runs over a pull request that never received it -- on the validating route
that is a fresh reviewer over the head it already rejected, then an approval
whose squash finds one commit, squashes nothing, and hands an unpushed head to
the docs pass.

An approved DEBT is one step further on. The write that approves a candidate
retires the generation in the same breath, deliberately and before the push,
so a tick that dies past it leaves no record to reconcile from at all -- only
an approval naming a commit the pull request never received, which nothing
under the stage reads.
"""
from __future__ import annotations

import unittest

from orchestrator.git.measurement.models import (
    FrozenCommit,
    MeasurementFailure,
)
from tests.workflow.stages.fixing import (
    fixing_test_support as fixing,
    published_gate_support as support,
)
from tests.workflow.stages.fixing.test_late_dispatch import (
    MOVED_CANDIDATE,
    _FrozenPairMixin,
)

ISSUE = fixing.ISSUE
VALIDATING = fixing.VALIDATING
MEASURED_CANDIDATE_SHA = support.MEASURED_CANDIDATE_SHA
PUSH_BRANCH = fixing.PUSH_BRANCH

KEY_SOURCE_STAGE = support.KEY_SOURCE_STAGE
KEY_RECEIPT_SHA = support.KEY_RECEIPT_SHA
KEY_APPROVED_SHA = support.KEY_APPROVED_SHA
KEY_APPROVED_LEASE = support.KEY_APPROVED_LEASE

# The prefix every field one generation owns is spelled with: dropping them is
# what the write that approves a small candidate does.
LATE_PREFIX = "late_"

# A revision this host cannot peel to a commit, for the checkout a rebuild or
# a prune left without the object the approval names.
CANDIDATE_ABSENT = MeasurementFailure.CANDIDATE_ABSENT

# The two keywords a gated push names its commit and pins its ref by.
REVISION = "revision"
LEASE = "force_with_lease"


def _pinned(github) -> dict:
    """The pinned comment this issue carries, read back after a tick."""
    return github.pinned_data(ISSUE)


def _assert_the_approval_stands(test_case, github) -> None:
    """The debt and its lease left as they were, and no receipt beside them.

    What makes the retry free: it asks for the same commit against the same
    head, and nothing on the comment claims a publication that never reached
    the remote.
    """
    pinned = _pinned(github)
    test_case.assertTrue(pinned[fixing.AWAITING_HUMAN])
    test_case.assertEqual(pinned[KEY_APPROVED_SHA], MEASURED_CANDIDATE_SHA)
    test_case.assertEqual(pinned[KEY_APPROVED_LEASE], fixing.PR_HEAD_SHA)
    test_case.assertIsNone(pinned.get(KEY_RECEIPT_SHA))


class _ValidatingTickMixin(_FrozenPairMixin):
    """One issue routed the way the dispatcher routes it under review."""

    def _route_validating(self, github, **run_options):
        """Route the tick the way the dispatcher does for that stage."""
        return self._route(
            github, github.get_issue(ISSUE),
            handled=VALIDATING, **run_options,
        )


class ReconciledPublicationTest(unittest.TestCase, _ValidatingTickMixin):
    """What the stage behind a settled reading is handed, and what it is not.

    The reading is settled and the record is gone, so nothing goes back for
    the push it allowed. Left owed, the stage runs over a pull request the
    candidate never joined -- and on the validating route that is a fresh
    reviewer over the head it already rejected, then an approval whose squash
    finds one commit, squashes nothing, and hands an unpushed head to the docs
    pass, which reads it as recovered work and skips the pass entirely.
    """

    def test_a_retry_publishes_before_its_stage(self) -> None:
        # The push comes first and the reviewer runs behind it, over the same
        # pull request the tick that froze the pair would have handed it.
        github = self._frozen_on_validating()

        dispatched, mocks = self._route_validating(github)

        pushed = mocks[PUSH_BRANCH].call_args
        self.assertEqual(pushed.kwargs[REVISION], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.kwargs[LEASE], fixing.PR_HEAD_SHA)
        dispatched.assert_called_once()

    def test_a_retry_leaves_a_squashable_branch(self) -> None:
        # What the reviewer behind it goes on to do: approve, squash, hand
        # off. The squash's one-commit shortcut publishes nothing, so the head
        # it reports has to be one the remote already carries -- which is what
        # the receipt here says, and what an unpushed candidate would not.
        github = self._frozen_on_validating()

        self._route_validating(github)

        pinned = _pinned(github)
        self.assertEqual(pinned[KEY_RECEIPT_SHA], MEASURED_CANDIDATE_SHA)
        self.assertIsNone(pinned[KEY_APPROVED_SHA])

    def test_a_push_that_missed_stops_the_stage(self) -> None:
        # Settled and unpublished is the one shape the stage may not run
        # behind: the reading says the commit may join the pull request and
        # the pull request has not received it. The approval naming it stays
        # on the comment, which is what the retry publishes from.
        github = self._frozen_on_validating()

        dispatched, _mocks = self._route_validating(
            github, push_branch=False,
        )

        dispatched.assert_not_called()
        pinned = _pinned(github)
        self.assertTrue(pinned[fixing.AWAITING_HUMAN])
        self.assertEqual(pinned[KEY_APPROVED_SHA], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pinned[KEY_APPROVED_LEASE], fixing.PR_HEAD_SHA)

    def _frozen_on_validating(self):
        """A pair the crashed tick froze while the issue was under review."""
        github = self._frozen(label=VALIDATING)[0]
        pinned = _pinned(github)
        pinned[KEY_SOURCE_STAGE] = VALIDATING
        github.seed_state(ISSUE, **pinned)
        return github




class ApprovedDebtReconciliationTest(
    unittest.TestCase, _ValidatingTickMixin,
):
    """A commit the gate approved and its own tick never pushed.

    The write that approves a candidate retires the generation in the same
    breath, deliberately and before the push, so a tick that dies past it
    leaves nothing for the frozen-pair reading to answer -- only an approval
    naming a commit the pull request never received. Nothing under the stage
    reads that: `validating` spawns a reviewer over the head the pull request
    already has, and the merge gate behind it offers a human a pull request
    the work is not on.
    """

    def test_a_debt_is_paid_before_its_stage(self) -> None:
        # Under the id the gate decided about and the head it decided
        # against, both of which live only on the approval once the
        # generation that froze them is gone.
        github = self._owing_a_push()

        dispatched, mocks = self._route_validating(github)

        pushed = mocks[PUSH_BRANCH].call_args
        self.assertEqual(pushed.kwargs[REVISION], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.kwargs[LEASE], fixing.PR_HEAD_SHA)
        dispatched.assert_called_once()

    def test_a_paid_debt_leaves_a_receipt(self) -> None:
        # Nothing is measured again -- the gate already ruled on this commit
        # -- so what the tick spends is the debt itself, and what it leaves in
        # its place is the receipt saying which commit reached the remote.
        github = self._owing_a_push()

        self._route_validating(github)

        pinned = _pinned(github)
        self.assertIsNone(pinned[KEY_APPROVED_SHA])
        self.assertIsNone(pinned[KEY_APPROVED_LEASE])
        self.assertEqual(pinned[KEY_RECEIPT_SHA], MEASURED_CANDIDATE_SHA)

    def test_a_checkout_that_cannot_pay_stops(self) -> None:
        # An approval is a claim about ONE commit, so the only checkout it can
        # be paid from is the one standing on it. Standing elsewhere, the
        # debt still says a commit the pull request does NOT carry was
        # measured and allowed to join it -- so a handler run behind that
        # works from a publication the approved work is not on, and the
        # reviewer votes on a head nobody adjudicated.
        for evidence in (
            {"candidate_commit": FrozenCommit(sha=MOVED_CANDIDATE)},
            {"candidate_commit": FrozenCommit(failure=CANDIDATE_ABSENT)},
        ):
            with self.subTest(evidence=evidence):
                github = self._owing_a_push()

                dispatched, mocks = self._route_validating(
                    github, **evidence,
                )

                mocks[PUSH_BRANCH].assert_not_called()
                dispatched.assert_not_called()
                pinned = _pinned(github)
                self.assertTrue(pinned[fixing.AWAITING_HUMAN])
                self.assertEqual(
                    pinned[KEY_APPROVED_SHA], MEASURED_CANDIDATE_SHA,
                )

    def test_a_head_moved_between_the_reads_stops(self) -> None:
        # The proof this debt takes and the reading the gate takes behind it
        # are two reads of one writable checkout. Left unbound, a commit
        # landing in that window is what gets measured, pushed, and receipted
        # -- while the approval it was granted for is dropped as paid. The
        # pull request would then carry a commit nobody adjudicated, under a
        # record saying the approved one reached it.
        github = self._owing_a_push()

        dispatched, mocks = self._route_validating(
            github,
            candidate_commit=(
                FrozenCommit(sha=MEASURED_CANDIDATE_SHA),
                FrozenCommit(sha=MOVED_CANDIDATE),
            ),
        )

        mocks[PUSH_BRANCH].assert_not_called()
        dispatched.assert_not_called()
        _assert_the_approval_stands(self, github)

    def test_a_checkout_that_cannot_pay_says_once(self) -> None:
        # The condition is not one this process can repair -- an operator has
        # to put the checkout back -- so a fresh notice every poll would be a
        # mention nobody can answer any faster.
        github = self._owing_a_push()
        moved = {"candidate_commit": FrozenCommit(sha=MOVED_CANDIDATE)}
        self._route_validating(github, **moved)
        posted = len(github.get_issue(ISSUE).comments)

        self._route_validating(github, **moved)

        self.assertEqual(len(github.get_issue(ISSUE).comments), posted)

    def test_a_debt_that_missed_stops_the_stage(self) -> None:
        # Allowed and unpublished is the one shape the stage may not run
        # behind. The approval and its lease stay exactly as they are, which
        # is what makes the retry free.
        github = self._owing_a_push()

        dispatched, _mocks = self._route_validating(
            github, push_branch=False,
        )

        dispatched.assert_not_called()
        _assert_the_approval_stands(self, github)

    def _owing_a_push(self):
        """The pinned comment a crash past the approval write left behind."""
        github = self._frozen(label=VALIDATING)[0]
        pinned = {
            key: recorded
            for key, recorded in _pinned(github).items()
            if not key.startswith(LATE_PREFIX)
        }
        pinned[KEY_APPROVED_SHA] = MEASURED_CANDIDATE_SHA
        pinned[KEY_APPROVED_LEASE] = fixing.PR_HEAD_SHA
        github.seed_state(ISSUE, **pinned)
        return github
