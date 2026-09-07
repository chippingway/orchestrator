# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the approval a publication is owed under rests on, and who may say it.

An approval is spent by the tick that comes back after a crash, without asking
anybody, so the only thing that decides whether one may be spent is what it
RESTS on. The owner that grants an approval is the only one that knows, and
the records standing around it are the same on every road -- so the basis is
written with the approval rather than inferred from its neighbours, read
fail-closed like every other late field, and dropped in the write that spends
the pair it describes.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.stages.implementing import (
    late_parks as _parks,
    late_publication as _publication,
    late_push as _push,
    late_records as _records,
    late_verdict as _verdict,
    state as _state,
)
from tests.support.fakes import FakeGitHubClient, make_issue
from tests.workflow.fixtures import (
    _TEST_SPEC,
    LABEL_IMPLEMENTING,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
)

_ISSUE_NUMBER = 611
_LEASE_SHA = "9" * SHA_LENGTH
_WORKTREE = Path("/tmp/orchestrator-test-late-basis")

# What a hand edit and a build from somewhere else leave in the field: a value
# no vocabulary here carries, which reads back as no basis at all.
_NOT_A_BASIS = "an operator said so"

# The push that landed, named by the commit it sent and the head it was
# pinned against, which is what a settlement is asked to reconcile against.
_LANDED = _publication._PublishedCandidate(
    held=False, revision=MEASURED_CANDIDATE_SHA, lease=_LEASE_SHA,
)


def _approved(basis: _parks.LateApprovalBasis) -> PinnedState:
    """A pinned comment carrying one approval granted on that basis."""
    state = PinnedState(data={})
    _parks._approve(state, MEASURED_CANDIDATE_SHA, _LEASE_SHA, basis)
    return state


def _gate(state: PinnedState) -> _records._Gate:
    """The one candidate a debt is about to be recorded for."""
    github = FakeGitHubClient()
    issue = make_issue(_ISSUE_NUMBER, label=LABEL_IMPLEMENTING)
    github.add_issue(issue)
    return _records._Gate(
        gh=github,
        spec=_TEST_SPEC,
        issue=issue,
        state=state,
        worktree=_WORKTREE,
    )


class ApprovalBasisRecordTest(unittest.TestCase):
    """The three fields an approval is, written and dropped together."""

    def test_the_group_goes_down_together(self) -> None:
        # A lease with no approval names a head nobody owes a push for, an
        # approval whose lease was dropped force-pushes over whatever the pull
        # request has become, and one whose basis was dropped is a debt a
        # later tick has to guess the provenance of.
        state = _approved(_parks.LateApprovalBasis.ADJUDICATION)

        self.assertEqual(
            state.get(_state._APPROVED_SHA), MEASURED_CANDIDATE_SHA,
        )
        self.assertEqual(state.get(_state._APPROVED_LEASE), _LEASE_SHA)
        self.assertEqual(
            _parks._approved_basis(state),
            str(_parks.LateApprovalBasis.ADJUDICATION),
        )

    def test_every_basis_round_trips(self) -> None:
        # The wire value is what the pinned comment carries, so each member
        # has to read back as itself rather than as the enum's repr.
        for basis in _parks.LateApprovalBasis:
            with self.subTest(basis=str(basis)):
                self.assertEqual(
                    _parks._approved_basis(_approved(basis)), str(basis),
                )

    def test_a_value_from_nowhere_is_no_basis(self) -> None:
        # Read fail-closed like every other late field: a spelling this build
        # does not carry is a basis nothing checked, and what a reader owes
        # such a record is the answer it can still defend.
        state = _approved(_parks.LateApprovalBasis.AUTHORIZATION)
        state.set(_state._APPROVED_BASIS, _NOT_A_BASIS)

        self.assertEqual(_parks._approved_basis(state), "")

    def test_an_older_binarys_approval_says_nothing(self) -> None:
        # The compatibility answer, and the honest one: a comment written
        # before this field existed carries an approval and no account of its
        # grounds, so the reader falls back rather than guessing.
        state = PinnedState(data={_state._APPROVED_SHA: MEASURED_CANDIDATE_SHA})

        self.assertEqual(_parks._approved_basis(state), "")

    def test_the_drop_takes_the_basis_with_it(self) -> None:
        # The basis describes one approval and outlives none: left behind, it
        # would stand beside whatever debt this issue records next and claim
        # grounds nobody granted that one.
        state = _approved(_parks.LateApprovalBasis.AUTHORIZATION)

        _parks._forget_approval(state)

        self.assertIsNone(state.get(_state._APPROVED_SHA))
        self.assertIsNone(state.get(_state._APPROVED_BASIS))

    def test_an_operators_gesture_names_two(self) -> None:
        # The group readers ask about rather than either member, since what
        # they decide is whether a debt has to be revalidated. The gate's own
        # two are outside it: nobody's permission was involved, so the tick
        # after a crash owes nobody a question before it pushes.
        self.assertEqual(_parks.AUTHORIZED_BASES, frozenset((
            _parks.LateApprovalBasis.ADJUDICATION,
            _parks.LateApprovalBasis.AUTHORIZATION,
        )))


class StandingBasisTest(unittest.TestCase):
    """What the claim an unproven landing puts back rests on."""

    def test_it_carries_what_granted_the_debt(self) -> None:
        # The debt this write puts back is the one that was already there, so
        # what it rests on is whatever granted it. Re-decided instead, an
        # operator's bypass would be replaced by ordinary debt at exactly the
        # write a crash behind it makes spendable.
        for basis in _parks.LateApprovalBasis:
            with self.subTest(basis=str(basis)):
                self.assertEqual(
                    _parks._standing_basis(_approved(basis)), basis,
                )

    def test_a_record_that_cannot_say_is_unmeasured(self) -> None:
        # A comment that never said, one a hand edit moved outside the
        # vocabulary, and one the drop beside this has already taken: such a
        # push skipped no reading of its own, so the claim it leaves is the
        # ordinary unmeasured one and the reader falls back from there.
        for described, written in (
            ("never written", None),
            ("outside the vocabulary", _NOT_A_BASIS),
        ):
            with self.subTest(record=described):
                state = _approved(_parks.LateApprovalBasis.READING)
                state.set(_state._APPROVED_BASIS, written)

                self.assertEqual(
                    _parks._standing_basis(state),
                    _parks.LateApprovalBasis.UNMEASURED,
                )


class UnmeasuredDebtBasisTest(unittest.TestCase):
    """What a publication that skipped the reading records for itself.

    Every road reaching it is a record this workflow made for itself and
    re-derives on the next tick -- a rewrite permit, a supersession the switch
    let past, a receipt the remote already carries -- so each answers for its
    own bypass and the debt it leaves needs no revalidating.
    """

    def test_it_records_the_unmeasured_basis(self) -> None:
        gate = _gate(PinnedState(data={}))

        staged = _verdict._stages_unmeasured_debt(
            gate, MEASURED_CANDIDATE_SHA, _LEASE_SHA,
        )

        self.assertTrue(staged)
        self.assertEqual(
            _parks._approved_basis(gate.state),
            str(_parks.LateApprovalBasis.UNMEASURED),
        )

    def test_a_debt_already_standing_is_left(self) -> None:
        # The approval already names this commit, so there is nothing to
        # record -- and rewriting the basis here would relabel a debt an
        # operator's gesture is behind as one this workflow granted itself.
        gate = _gate(_approved(_parks.LateApprovalBasis.ADJUDICATION))

        staged = _verdict._stages_unmeasured_debt(
            gate, MEASURED_CANDIDATE_SHA, _LEASE_SHA,
        )

        self.assertFalse(staged)
        self.assertEqual(
            _parks._approved_basis(gate.state),
            str(_parks.LateApprovalBasis.ADJUDICATION),
        )


class PaidPublicationBasisTest(unittest.TestCase):
    """What survives the write that pays one debt and puts the next back.

    A push that landed drops the approval it was licensed by, and where the
    checkout it left is not provably what went out it records the same commit
    again as the head the pull request now stands on. Those are one write, so
    the grounds the second one rests on have to be read out of the record
    BEFORE the first takes them.
    """

    def test_the_replacement_claim_keeps_the_grounds(self) -> None:
        # Read after the drop, the claim would say `unmeasured` for a debt an
        # operator's gesture was behind -- and a record damaged in the window
        # behind this write would then be spent as ordinary debt by the tick
        # that comes back to it.
        for basis in _parks.AUTHORIZED_BASES:
            with self.subTest(basis=str(basis)):
                gate = _gate(_approved(basis))

                _push._publication_paid(gate, _LANDED, unproven=True)

                self.assertEqual(
                    _parks._approved_basis(gate.state), str(basis),
                )
                self.assertEqual(
                    gate.state.get(_state._APPROVED_SHA), MEASURED_CANDIDATE_SHA,
                )

    def test_a_proven_landing_leaves_no_debt(self) -> None:
        # The other exit: nothing is owed, so the whole group goes -- a basis
        # left behind would stand beside whatever this issue records next.
        gate = _gate(_approved(_parks.LateApprovalBasis.ADJUDICATION))

        _push._publication_paid(gate, _LANDED, unproven=False)

        self.assertIsNone(gate.state.get(_state._APPROVED_SHA))
        self.assertIsNone(gate.state.get(_state._APPROVED_BASIS))


if __name__ == "__main__":
    unittest.main()
