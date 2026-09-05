# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Where an interrupted rebase carrying a verdict stopped, and what finishes it.

One auto rebase of an adjudicated commit is six durable moments in a row --
the anchor, the rewrite, the permission, the push, the receipt, and the route
-- and a process can be lost in any window between them. What the next tick
comes back to is a checkout on the replay and a comment that got as far as it
got, and the whole of what these cases pin is that each of those states
resolves into exactly one finish.

Two readings decide it. The REMOTE says which effect the dead tick reached:
still on the anchor and the push never went out, on the replay and it did,
anywhere else and somebody moved the branch. The pinned comment says which of
the transfer's own writes it reached. Neither is enough alone -- a remote
carrying the replay with the permission still outstanding is a receipt this
tick owes, and the same remote past that receipt is a route to finish and
nothing more.

What none of them may do is start over. A replay of the exact change a human
already ruled on must not spawn an agent, take a measurement, rebase again,
force-rewrite a branch the remote already has, or put a second adjudication on
the thread -- and the states nobody can vouch for keep the fail-closed park or
reset they always had.
"""
from __future__ import annotations

import unittest

from orchestrator.workflow.late_split import (
    exemption as _exemption,
    rewrites as _rewrites,
)
from tests.git.base_sync.exemption_test_support import (
    EVENT_MEASUREMENT,
    EVENT_TRANSFER,
    LEASE,
    RECOVERY_PUSHED,
    RECOVERY_RELABELLED,
    REVISION,
    _CleanRebaseCase,
    adjudicated,
)
from tests.git.base_sync.refresh_scenarios import PUSH_PATCH
from tests.git.base_sync.refresh_test_support import (
    AFTER_SHA,
    BEFORE_SHA,
    EVENT_BASE_REBASED,
    HARD_RESET_FLAG,
    ISSUE,
    KEY_PARK_REASON,
    KEY_PENDING_PUSH_SHA,
    KEY_REVIEW_ROUND,
    LABEL_VALIDATING,
    METHOD_FIELD,
    PARK_PUSH_FAILED,
    RESET_COMMAND,
)
from tests.workflow.fixtures import LABEL_DECOMPOSING

# A commit neither this issue nor its recovery put on the branch, which is
# what an out-of-band update to the pull request looks like from here.
FOREIGN_SHA = "f0000000" * 5

# The field a hand edit takes out of an authorization group, leaving a claim
# about this issue's exemption that nothing can read back whole.
DAMAGED_FIELD = "late_rewrite_to_base_sha"

# The leftovers that make a checkout something no contribution may be
# fingerprinted beside.
LOOSE_EDITS = ("scratch.txt",)

# The scenario alias the hardened git seam is installed under, which is what
# a reset that never happened is read back off.
HARDENED_PATCH = "hardened"


class _ResumedRebaseCase(_CleanRebaseCase):
    """One adjudicated rebase stopped mid-tick and resumed on the next one."""

    def setUp(self) -> None:
        super().setUp()
        adjudicated(self)

    def _assert_finished_the_route(self, method: str) -> None:
        """The anchor is gone, the round is reset, and review has the head."""
        pinned = self.gh.pinned_data(ISSUE)
        self.assertIsNone(pinned[KEY_PENDING_PUSH_SHA])
        self.assertEqual(pinned[KEY_REVIEW_ROUND], 0)
        self.assertIn((ISSUE, LABEL_VALIDATING), self.gh.label_history)
        rebased = self._events_of(EVENT_BASE_REBASED)
        self.assertEqual(rebased[-1][METHOD_FIELD], method)

    def _assert_settled_once(self) -> None:
        """The verdict is on the replay, and it was moved exactly once."""
        durable = self._durable()
        self.assertTrue(_exemption.is_exempt(durable, AFTER_SHA))
        self.assertEqual(
            _rewrites.read_rewrite_authorization(durable).phase,
            _rewrites.LateRewritePhase.PUBLISHED,
        )
        self.assertEqual(len(self._events_of(EVENT_TRANSFER)), 1)

    def _assert_nothing_readjudicated(self) -> None:
        """No agent, no reading, and no second question for a human."""
        self.assertEqual(self._events_of(EVENT_MEASUREMENT), [])
        self.assertNotIn((ISSUE, LABEL_DECOMPOSING), self.gh.label_history)


class UnrecordedRewriteRecoveryTest(_ResumedRebaseCase, unittest.TestCase):
    """The rewrite that reached the branch before any permission reached disk."""

    def setUp(self) -> None:
        super().setUp()
        self._crashes_before_the_grant()
        self.resumed = self._resumes()

    def test_the_crash_left_no_claim_behind(self) -> None:
        # The premise: the replay is on the branch and the comment says
        # nothing about it, so the record cannot supply the evidence and a
        # recovery that asked it would measure an adjudicated change afresh.
        self.assertFalse(
            _rewrites.carries_rewrite_authorization(self._crashed),
        )
        self.assertEqual(
            self._crashed.get(KEY_PENDING_PUSH_SHA), BEFORE_SHA,
        )

    def test_the_recovery_re_derives_and_settles(self) -> None:
        # Assembled from the same four readings the dead tick would have
        # used, and decided by the same permit: the push is named against the
        # replay and pinned to the anchor the remote is still standing on.
        pushed = self.resumed[PUSH_PATCH].call_args.kwargs
        self.assertEqual(pushed[REVISION], AFTER_SHA)
        self.assertEqual(pushed[LEASE], BEFORE_SHA)
        self._assert_settled_once()

    def test_the_replay_is_not_measured_again(self) -> None:
        self._assert_nothing_readjudicated()
        self._assert_finished_the_route(RECOVERY_PUSHED)

    def _crashes_before_the_grant(self) -> None:
        super()._crashes_before_the_grant()
        self._crashed = self._durable()


class OutstandingPermissionRecoveryTest(_ResumedRebaseCase, unittest.TestCase):
    """The tick that dies between the grant and the push it licensed."""

    def setUp(self) -> None:
        super().setUp()
        self._crashes_before_the_push()
        self.resumed = self._resumes()

    def test_the_recovery_publishes_and_settles(self) -> None:
        # The permit is re-asked over the record the grant left -- the
        # recovery has no evidence of its own -- and the receipt behind the
        # reissued push is what finally carries the verdict over.
        pushed = self.resumed[PUSH_PATCH].call_args.kwargs
        self.assertEqual(pushed[REVISION], AFTER_SHA)
        self.assertEqual(pushed[LEASE], BEFORE_SHA)
        self._assert_settled_once()

    def test_the_refresh_tail_is_finished(self) -> None:
        # The debt the grant recorded is what freezes this branch, and it
        # freezes it out of the very recovery the anchor beside it exists for.
        # Left there, a later stage lands the push and the reviewer is never
        # routed at the rewritten head.
        self._assert_nothing_readjudicated()
        self._assert_finished_the_route(RECOVERY_PUSHED)


class LandedPushRecoveryTest(_ResumedRebaseCase, unittest.TestCase):
    """The push that reached the remote and lost the write that receipts it."""

    def setUp(self) -> None:
        super().setUp()
        # The request went out and the process died waiting for its answer,
        # so the pull request carries the replay while the comment still says
        # a push is owed for it.
        self._crashes_before_the_push()
        self.resumed = self._resumes(remote_head=AFTER_SHA)

    def test_the_settlement_rewrites_nothing(self) -> None:
        # The remote is already standing on the replay, so the push is the
        # leased no-op that proves it: named against that commit and pinned to
        # it, which is a request with nothing to send rather than a second
        # force-rewrite of a branch the pull request already has.
        pushed = self.resumed[PUSH_PATCH].call_args.kwargs
        self.assertEqual(pushed[REVISION], AFTER_SHA)
        self.assertEqual(pushed[LEASE], AFTER_SHA)

    def test_the_receipt_carries_the_verdict_over(self) -> None:
        self._assert_settled_once()
        self.assertEqual(
            self._events_of(EVENT_TRANSFER)[0]["transfer_proof"],
            str(_rewrites.LateRewriteProof.ALREADY_PUBLISHED),
        )

    def test_the_route_finishes_untouched(self) -> None:
        self._assert_nothing_readjudicated()
        self._assert_finished_the_route(RECOVERY_RELABELLED)


class SettledHandoffRecoveryTest(_ResumedRebaseCase, unittest.TestCase):
    """The transfer that finished, on a tick that never finished its route."""

    def setUp(self) -> None:
        super().setUp()
        self._crashes_before_the_route()
        self.resumed = self._resumes(remote_head=AFTER_SHA)

    def test_nothing_is_pushed_or_moved_a_second_time(self) -> None:
        # The receipt landed with the rotation on it, so every question this
        # recovery could ask is already answered: there is no permission left
        # outstanding, nothing to send, and nothing to report twice.
        self.resumed[PUSH_PATCH].assert_not_called()
        self._assert_settled_once()

    def test_only_the_route_is_finished(self) -> None:
        self._assert_nothing_readjudicated()
        self._assert_finished_the_route(RECOVERY_RELABELLED)


class FailClosedRecoveryTest(_ResumedRebaseCase, unittest.TestCase):
    """The states nobody can vouch for keep the answer they always had."""

    def test_a_moved_remote_rolls_the_permission_back(self) -> None:
        # Somebody pushed to the branch while the interrupted tick was down,
        # so the replay may not be published over them. The reset puts the
        # branch back on the commit the exemption never left, and the
        # permission goes with the object no branch has any more.
        self._crashes_before_the_push()

        self._resumes(remote_head=FOREIGN_SHA, diverged=(1, 1))

        durable = self._durable()
        self.assertTrue(_exemption.is_exempt(durable, BEFORE_SHA))
        self.assertFalse(_rewrites.carries_rewrite_authorization(durable))
        self.assertEqual(
            self.gh.pinned_data(ISSUE)[KEY_PARK_REASON], PARK_PUSH_FAILED,
        )

    def test_an_unreadable_permission_settles_nothing(self) -> None:
        # A group this build cannot read back whole is the only account there
        # is of how the exemption came to name what it names, so the recovery
        # finishes the route and leaves the record exactly as it stands rather
        # than settling a transfer nobody can check.
        self._crashes_before_the_push()
        self._damages_the_permission()

        resumed = self._resumes(remote_head=AFTER_SHA)

        resumed[PUSH_PATCH].assert_not_called()
        self._assert_untouched_transfer()

    def test_a_loose_checkout_settles_nothing(self) -> None:
        # The pull request carries the replay and is right either way, so
        # there is nothing to reset and nothing to park over -- but a
        # contribution fingerprinted beside changes nobody committed is not
        # the one that was published, so the permission is left standing.
        self._crashes_before_the_push()

        resumed = self._resumes(remote_head=AFTER_SHA, dirty=LOOSE_EDITS)

        resumed[PUSH_PATCH].assert_not_called()
        self._assert_untouched_transfer()

    def test_a_refused_no_op_parks_in_place(self) -> None:
        # The pull request was standing on the replay when this tick read it
        # and refused the lease a moment later, so the remote moved in
        # between. The checkout is on the commit the pull request was
        # carrying, so nothing is reset off it and the anchor stays pinned for
        # the next tick to classify the remote afresh.
        self._crashes_before_the_push()

        resumed = self._resumes(remote_head=AFTER_SHA, push=False)

        pinned = self.gh.pinned_data(ISSUE)
        self.assertEqual(pinned[KEY_PENDING_PUSH_SHA], BEFORE_SHA)
        self.assertEqual(pinned[KEY_PARK_REASON], PARK_PUSH_FAILED)
        self.assertEqual(self._resets_of(resumed), [])
        self.assertEqual(self._events_of(EVENT_TRANSFER), [])

    def _resets_of(self, resumed) -> list:
        """Every hard reset the hardened git seam was asked for this tick."""
        return [
            recorded for recorded in resumed[HARDENED_PATCH].call_args_list
            if recorded.args[:2] == (RESET_COMMAND, HARD_RESET_FLAG)
        ]

    def _damages_the_permission(self) -> None:
        """Take one field out of the group the grant left on the comment."""
        issue = self.gh._issues[ISSUE]
        state = self.gh.read_pinned_state(issue)
        state.data.pop(DAMAGED_FIELD)
        self.gh.write_pinned_state(issue, state)

    def _assert_untouched_transfer(self) -> None:
        """The verdict is where the adjudication put it and nothing reported."""
        durable = self._durable()
        self.assertTrue(_exemption.is_exempt(durable, BEFORE_SHA))
        self.assertTrue(_rewrites.carries_rewrite_authorization(durable))
        self.assertEqual(self._events_of(EVENT_TRANSFER), [])
        self._assert_nothing_readjudicated()
        self._assert_finished_the_route(RECOVERY_RELABELLED)


if __name__ == "__main__":
    unittest.main()
