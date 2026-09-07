# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The debt an unmeasured publication records, and the write that pays it.

A candidate that skips the reading freezes no generation for itself, so between
the gate letting it through and the push that carries it there is committed
work on the branch and, without this, nothing on the issue naming it. The
measured road records that debt beside its retirement; these pin down that the
unmeasured roads -- an adjudication's exemption, a supersession the switch let
past -- record it too.

Both sides of the push are here because the windows are different. Before the
settlement write the branch may already be on the remote with nothing saying
so, and the debt is the whole of what a later tick has to go on. After it, the
receipt and the route's own bookkeeping are already durable and only the
caller's tail is missing.

The receipt is what makes the second window easy to miss: it is never cleared,
so a branch that has been on the remote before arrives with it already naming
the commit in hand. It says nothing about the round behind this push, and the
debt recorded ahead of the push is what the settlement reads instead.
"""
from __future__ import annotations

import unittest
from functools import partial

from orchestrator.workflow.late_split import overrides as _overrides
from orchestrator.workflow.stages.implementing import (
    late_authority as _late_authority,
    late_debt as _late_debt,
    late_parks as _parks,
    late_push as _late_push,
    late_reconcile as _late_reconcile,
)
from tests.workflow.fixtures import _authorized_exemption
from tests.workflow.interleaving import _AnswersOnce, _RacesTheStep
from tests.workflow.observation_support import ObservedCloseCase
from tests.workflow.repo_values import TEST_REPO_SLUG
from tests.workflow.stages.fixing import (
    fixing_test_support as fixing,
    published_gate_support as support,
)
from tests.workflow.stages.fixing.test_late_dispatch import (
    _FrozenPairMixin,
)

ISSUE = fixing.ISSUE
PR_NUMBER = fixing.PR_NUMBER
PR_HEAD_SHA = fixing.PR_HEAD_SHA
PUSH_BRANCH = fixing.PUSH_BRANCH
RUN_AGENT = fixing.RUN_AGENT
REVIEW_ROUND = fixing.REVIEW_ROUND
PENDING_FIX_AT = fixing.PENDING_FIX_AT
VALIDATING = fixing.VALIDATING
patch = fixing.patch

# The two keywords a gated push names its commit and pins its ref by.
REVISION = "revision"
LEASE = "force_with_lease"

MEASURED_CANDIDATE_SHA = support.MEASURED_CANDIDATE_SHA
_SizeGateFixtureMixin = support._SizeGateFixtureMixin
config = fixing.config

PUBLICATION_PAID = "_publication_paid"
TICK_DIED = "the tick died around the settlement"

KEY_SPENDS = "late_spends"

# What the approval a publication records rests on: an operator's gesture
# rather than a count this gate took, which is what keeps a record damaged in
# the crash window behind it from being spent as ordinary debt.
KEY_APPROVED_BASIS = "late_approved_basis"

# What the in_review fix route leaves `review_round` at: reset to zero, since
# the round before the fix is the one the reviewer approved.
SPENT_ROUND = 0

# What the seed carries before the push, so a round that never reached the
# comment is told from one that did.
UNSPENT_ROUND = 1


class _DiesAroundTheSettlement:
    """A tick that stops on one side or the other of the receipt's write.

    `settling` says whether that write runs first, which is what tells the two
    windows apart: the push has landed either way, and what differs is whether
    anything on the pinned comment says so.
    """

    def __init__(self, *, settling: bool) -> None:
        self._paid = _late_push._publication_paid
        self._settling = settling

    def __call__(self, gate, published, unproven) -> None:
        if self._settling:
            self._paid(gate, published, unproven)
        raise RuntimeError(TICK_DIED)


class UnmeasuredDebtTest(unittest.TestCase, _SizeGateFixtureMixin):
    """What an unmeasured push leaves behind on each side of its own write."""

    def test_the_debt_goes_down_before_the_push(self) -> None:
        # The window the reviewer of a crashed tick has nothing else to read:
        # the branch is on the remote and the settlement never ran. With no
        # generation frozen and no debt recorded, the next tick finds an issue
        # with nothing owed and runs the stage -- spawning an agent over work
        # nobody can say is unpublished. The debt is what it reads instead.
        scenario = self._exempt_publication()

        self._crashes(scenario, settling=False)

        pinned = self._pinned(scenario)
        self.assertEqual(
            pinned[support.KEY_APPROVED_SHA], MEASURED_CANDIDATE_SHA,
        )
        self.assertEqual(pinned[support.KEY_APPROVED_LEASE], PR_HEAD_SHA)

    def test_the_debt_carries_what_the_route_owed(self) -> None:
        # The recovery has no run behind it to re-derive a reviewer round or a
        # consumed fix batch from, so the obligations ride the same write the
        # debt does and are spent by the push that pays it.
        scenario = self._exempt_publication()

        self._crashes(scenario, settling=False)

        self.assertIn(
            [REVIEW_ROUND, SPENT_ROUND], self._pinned(scenario)[KEY_SPENDS],
        )

    def test_the_settlement_closes_the_debt(self) -> None:
        # The far side of the same write: the receipt names what reached the
        # remote, the debt is gone because it is paid, and what the route owed
        # is on the comment rather than waiting for the caller's own write.
        scenario = self._exempt_publication()

        self._crashes(scenario, settling=True)

        pinned = self._pinned(scenario)
        self.assertEqual(
            pinned[support.KEY_RECEIPT_SHA], MEASURED_CANDIDATE_SHA,
        )
        self.assertIsNone(pinned[support.KEY_APPROVED_SHA])
        self.assertEqual(pinned[REVIEW_ROUND], SPENT_ROUND)
        self.assertIsNone(pinned[PENDING_FIX_AT])

    def test_an_uncrashed_push_hands_the_issue_on(self) -> None:
        # What says the two crashes above are about the window rather than
        # about the publication refusing to finish: unmeasured, pushed, the
        # round closed, and the reviewer given the head it was told about.
        scenario = self._exempt_publication()

        mocks = self._run_fix_round(scenario)

        mocks[support.COUNT_ADDED_LINES].assert_not_called()
        mocks[PUSH_BRANCH].assert_called_once()
        self.assertEqual(self._pinned(scenario)[REVIEW_ROUND], SPENT_ROUND)
        self.assertIn((ISSUE, VALIDATING), scenario.github.label_history)

    def _crashes(self, scenario, *, settling: bool) -> None:
        """Kill the tick on one side of the write the receipt rides."""
        with patch.object(
            _late_push, PUBLICATION_PAID,
            _DiesAroundTheSettlement(settling=settling),
        ), self.assertRaises(RuntimeError):
            self._run_fix_round(scenario)

    def _exempt_publication(self):
        """A fix round publishing a commit an adjudication already accepted.

        Nothing measures it and no generation is frozen for it, so the debt
        this records is the only account of the work between the gate and the
        push. The pull request is standing somewhere else, which is what makes
        this push an event with a window rather than a republication of one
        the remote already has.

        The receipt already names the commit, because it is never cleared and
        this branch has been on the remote before. On its own it says nothing
        about the round behind THIS push, so a settlement that read it as
        "nothing left to close" would leave that round for the caller's write
        a tick's work later.
        """
        return self._seed_fix_round(**{
            **_authorized_exemption(),
            support.KEY_RECEIPT_SHA: MEASURED_CANDIDATE_SHA,
            REVIEW_ROUND: UNSPENT_ROUND,
        })


class SwitchedOffDebtTest(unittest.TestCase, _SizeGateFixtureMixin):
    """The same debt where the switch keeps the candidate out of the gate.

    Nothing freezes a publication there: no pull request is read and this
    owner establishes no head of its own. The push still MOVES one all the
    same -- the caller read the head it is replacing and the force-push is
    pinned to it -- so the window between that push and the receipt is the
    window every other unmeasured publication has, and the debt is recorded
    against the caller's own lease. What `DECOMPOSE=off` decides is the
    measurement; the account of what a push is putting where is not its to
    turn off.
    """

    def test_the_debt_goes_down_before_the_push(self) -> None:
        scenario = self._seed_fix_round(**{REVIEW_ROUND: UNSPENT_ROUND})

        with patch.object(config, support.DECOMPOSE, False):
            self._crashes(scenario, settling=False)

        pinned = self._pinned(scenario)
        self.assertEqual(
            pinned[support.KEY_APPROVED_SHA], MEASURED_CANDIDATE_SHA,
        )
        self.assertEqual(pinned[support.KEY_APPROVED_LEASE], PR_HEAD_SHA)
        self.assertIn([REVIEW_ROUND, SPENT_ROUND], pinned[KEY_SPENDS])

    def test_the_switch_still_reads_nothing(self) -> None:
        # What says the debt is not the gate creeping back in: no pull request
        # is measured, and the push goes out named against the checkout and
        # pinned to the head the round began at.
        scenario = self._seed_fix_round(**{REVIEW_ROUND: UNSPENT_ROUND})

        with patch.object(config, support.DECOMPOSE, False):
            mocks = self._run_fix_round(scenario)

        mocks[support.COUNT_ADDED_LINES].assert_not_called()
        pushed = mocks[PUSH_BRANCH].call_args
        self.assertEqual(pushed.kwargs[REVISION], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.kwargs[LEASE], PR_HEAD_SHA)

    def test_an_authorized_debt_still_says_so(self) -> None:
        # The switch decides the MEASUREMENT, not what a debt rests on. An
        # authorized exemption is answered before the switch is asked at all,
        # so this road leaves an operator's debt like any other -- and
        # recorded as ordinary unmeasured debt it would be spent by the tick
        # after the crash without anybody being asked.
        scenario = self._seed_fix_round(**_authorized_exemption())

        with patch.object(config, support.DECOMPOSE, False):
            self._crashes(scenario, settling=False)

        self.assertEqual(
            self._pinned(scenario)[KEY_APPROVED_BASIS],
            str(_parks.LateApprovalBasis.AUTHORIZATION),
        )

    def test_a_damaged_one_is_measured_on_restart(self) -> None:
        # The whole of what that basis buys, end to end: the crash leaves the
        # debt, the authorization is damaged behind it, and the tick that
        # comes back with the gate switched on measures the candidate instead
        # of spending a bypass nothing can show the terms of.
        scenario = self._seed_fix_round(**_authorized_exemption())
        with patch.object(config, support.DECOMPOSE, False):
            self._crashes(scenario, settling=False)
        self._damage_the_authorization(scenario)

        with patch.object(config, support.MAX_ADDED_LINES, support.CEILING):
            mocks = self._run_fix_round(
                scenario, added_lines=support.PAST_THE_CEILING,
            )

        mocks[support.COUNT_ADDED_LINES].assert_called_once()
        self._assert_unpushed(mocks)

    def _damage_the_authorization(self, scenario) -> None:
        """What a hand edit between the crash and the retry leaves behind."""
        state = scenario.github.read_pinned_state(scenario.issue)
        state.set(_overrides.LATE_OVERRIDE_FINGERPRINT, None)
        scenario.github.write_pinned_state(scenario.issue, state)

    _crashes = UnmeasuredDebtTest._crashes


class _ReconciliationCase(
    unittest.TestCase, _SizeGateFixtureMixin, _FrozenPairMixin,
):
    """A fix round routed the way a whole tick routes one.

    The two mixins together, because the reconciliation is only reachable
    through the dispatcher and only seedable through the fix round: one owns
    the seed and the gate assertions, the other the routing and the frozen
    pair. Named rather than repeated so a case about the same window adds a
    base of its own instead of a fourth.
    """


class UnmeasuredDebtBasisTest(_ReconciliationCase):
    """Whose decision the debt an unmeasured publication leaves rests on.

    An approval is spent by the tick that comes back after a crash without
    anybody being asked, so what it RESTS on is the whole of what decides
    whether it may be. This publication is an operator's rather than the
    gate's own count, and the record has to say so on both sides of the write
    that pays it.
    """

    def test_the_debt_says_what_it_rests_on(self) -> None:
        # This one is an operator's rather than the gate's, and the record has
        # to say so. Written as ordinary unmeasured debt it would be spent by
        # the tick after the crash without anybody being asked -- so an
        # authorization damaged in that same window would bypass the
        # cumulative gate as though this gate had counted the change.
        scenario = self._exempt_publication()

        self._crashes(scenario, settling=False)

        self.assertEqual(
            self._pinned(scenario)[KEY_APPROVED_BASIS],
            str(_parks.LateApprovalBasis.AUTHORIZATION),
        )

    def test_a_second_proof_cannot_downgrade_it(self) -> None:
        # The gate admits this candidate on a proof it took itself, and the
        # debt records THAT answer rather than one taken again at the write.
        # Asked twice, a store that stopped answering in between would record
        # an operator's bypass as ordinary unmeasured debt -- and the tick
        # after this crash spends ordinary debt without asking anyone.
        scenario = self._exempt_publication()
        proving = _AnswersOnce(
            _late_authority._contributes_what_was_authorized, False,
        )

        with patch.object(
            _late_authority, "_contributes_what_was_authorized", proving,
        ):
            self._crashes(scenario, settling=False)

        self.assertEqual(
            self._pinned(scenario)[KEY_APPROVED_BASIS],
            str(_parks.LateApprovalBasis.AUTHORIZATION),
        )

    def test_an_unproven_landing_keeps_that_basis(self) -> None:
        # The push landed and the checkout stopped being what went out, so the
        # claim goes back for the commit now on the pull request. What it
        # rests on is what the debt it replaces rested on, read BEFORE the
        # write that pays and drops that debt -- read after, an operator's
        # gesture would be recorded as ordinary unmeasured debt and spent by
        # the next tick without anybody being asked.
        scenario = self._exempt_publication()

        self._run_fix_round(
            scenario,
            candidate_commit=(
                support.FrozenCommit(sha=MEASURED_CANDIDATE_SHA),
                support.FrozenCommit(sha=support.MOVED_AFTER_PUSH),
            ),
        )

        pinned = self._pinned(scenario)
        self.assertEqual(
            pinned[support.KEY_APPROVED_SHA], MEASURED_CANDIDATE_SHA,
        )
        self.assertEqual(
            pinned[KEY_APPROVED_BASIS],
            str(_parks.LateApprovalBasis.AUTHORIZATION),
        )


    _crashes = UnmeasuredDebtTest._crashes
    _exempt_publication = UnmeasuredDebtTest._exempt_publication


class UnmeasuredDebtRetryTest(_ReconciliationCase):
    """The tick after the one that pushed and recorded nothing else."""

    def test_the_retry_publishes_it_first(self) -> None:
        # The reconciliation ahead of every handler finds the debt and
        # republishes the same commit against the same head -- BEFORE the
        # stage runs, which is the whole point: without it the stage reads an
        # issue that has published nothing, resumes a developer over the head
        # the pull request already has, and hands the gate a commit whose two
        # readings of that publication no longer agree.
        scenario = self._crashed_before_the_settlement()

        mocks = self._route_to_the_stage(
            scenario.github, scenario.github.get_issue(ISSUE),
        )

        first = mocks[PUSH_BRANCH].call_args_list[0]
        self.assertEqual(first.kwargs[REVISION], MEASURED_CANDIDATE_SHA)
        self.assertEqual(first.kwargs[LEASE], PR_HEAD_SHA)

    def test_the_retry_closes_what_the_debt_carried(self) -> None:
        # And the recovery closes it: the receipt names what reached the
        # remote, the debt is gone, and the round the dead tick spent is
        # counted once rather than left for a stage that cannot re-derive it.
        scenario = self._crashed_before_the_settlement()

        self._route_to_the_stage(
            scenario.github, scenario.github.get_issue(ISSUE),
        )

        pinned = self._pinned(scenario)
        self.assertEqual(
            pinned[support.KEY_RECEIPT_SHA], MEASURED_CANDIDATE_SHA,
        )
        self.assertIsNone(pinned[support.KEY_APPROVED_SHA])
        self.assertEqual(pinned[REVIEW_ROUND], SPENT_ROUND)

    def test_a_closed_issue_publishes_nothing(self) -> None:
        # The same crash window with the issue closed in it. Everything this
        # reconciliation does ends in a push, and the terminal that drains a
        # closed issue runs INSIDE the stage handler -- behind it. Answered
        # there, the debt would put work on a pull request nobody wants, one
        # tick before the finalizer said so. Handing it back costs nothing:
        # the record, the branch and the debt are left exactly as they are for
        # that terminal to drain.
        scenario = self._crashed_before_the_settlement()
        scenario.issue.closed = True

        mocks = self._route_to_the_stage(
            scenario.github, scenario.github.get_issue(ISSUE),
        )

        mocks[PUSH_BRANCH].assert_not_called()
        self.assertEqual(
            self._pinned(scenario)[support.KEY_APPROVED_SHA],
            MEASURED_CANDIDATE_SHA,
        )

    def _crashed_before_the_settlement(self):
        """One tick that pushed and died before it recorded anything."""
        scenario = self._exempt_publication()
        self._crashes(scenario, settling=False)
        return scenario

    _crashes = UnmeasuredDebtTest._crashes
    _exempt_publication = UnmeasuredDebtTest._exempt_publication


class ClosedMidFlightTest(ObservedCloseCase, _ReconciliationCase):
    """A close a poll observes while this reconciliation is in flight.

    The guard at the reconciliation's door reads the issue OBJECT, which is
    the snapshot the tick opened with. Everything between it and the push --
    a worktree probe, a head read, a status read on the debt road, and the
    whole gated reading on the frozen-pair road -- is time another worker's
    poll can find the issue closed in, and a close there would be answered one
    push too late, on a pull request nobody wants.
    """

    def setUp(self) -> None:
        self._fresh_process()

    def test_a_close_mid_debt_publishes_nothing(self) -> None:
        scenario = self._crashed_before_the_settlement()

        with self._racing(_late_debt, "_unpayable_debt"):
            mocks = self._route_to_the_stage(
                scenario.github, scenario.github.get_issue(ISSUE),
            )

        mocks[PUSH_BRANCH].assert_not_called()
        mocks[RUN_AGENT].assert_not_called()
        self.assertEqual(
            self._pinned(scenario)[support.KEY_APPROVED_SHA],
            MEASURED_CANDIDATE_SHA,
        )

    def test_a_close_stops_the_tick_it_landed_in(self) -> None:
        # Refusing the push is half of what the latch owes. The other half is
        # STOPPING: the reconciliation runs ahead of the stage handler, so a
        # refusal handed back as "nothing to do here" leaves the tick going.
        # The terminal in front of the handler reads the issue OBJECT this
        # tick opened with, which still says open, so it finds nothing to
        # finalize and the handler behind it spawns an agent on an issue
        # somebody closed. What advances the issue instead is the cleanup pass
        # every latched close is owed, which is what settles the latch.
        scenario = self._crashed_before_the_settlement()

        with self._racing(_late_debt, "_unpayable_debt"):
            dispatched = self._route(
                scenario.github, scenario.github.get_issue(ISSUE),
            )[0]

        dispatched.assert_not_called()

    def test_a_close_mid_reading_publishes_nothing(self) -> None:
        # The frozen-pair road, whose window is wider still: the reading
        # itself is behind the guard, so a close can land while the remote is
        # being asked for the base.
        scenario = self._seed_fix_round(**support.recorded_generation())

        with self._racing(_late_reconcile, "_answers_the_frozen_pair"):
            mocks = self._route_to_the_stage(
                scenario.github, scenario.github.get_issue(ISSUE),
            )

        mocks[support.COUNT_ADDED_LINES].assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()
        mocks[RUN_AGENT].assert_not_called()

    def test_a_close_at_the_push_seam_holds(self) -> None:
        # The last window of all, and the narrowest one the code can observe:
        # the latch lands on the step immediately before the branch update,
        # past every guard the roads above this asked. A push there is the one
        # thing a closed issue may never earn, and nothing further along could
        # refuse it -- the next call IS the update.
        scenario = self._crashed_before_the_settlement()

        with self._racing(_late_push, "_repinned"):
            mocks = self._route_to_the_stage(
                scenario.github, scenario.github.get_issue(ISSUE),
            )

        mocks[PUSH_BRANCH].assert_not_called()

    def _racing(self, owner, step: str):
        """A poll that latches the close the instant that step runs."""
        return patch.object(owner, step, _RacesTheStep(
            getattr(owner, step),
            partial(self._latch_close, TEST_REPO_SLUG, ISSUE),
        ))

    _crashed_before_the_settlement = (
        UnmeasuredDebtRetryTest._crashed_before_the_settlement
    )
    _crashes = UnmeasuredDebtTest._crashes
    _exempt_publication = UnmeasuredDebtTest._exempt_publication


if __name__ == "__main__":
    unittest.main()
