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

import itertools
import unittest

from orchestrator.git.base_sync import transfers
from orchestrator.git.base_sync.models import _AutoRebaseRecoveryContext
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    rewrites as _rewrites,
)
from orchestrator.workflow.state import WorkflowLabel
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
    LABEL_IN_REVIEW as LABEL,
    LABEL_VALIDATING,
    METHOD_FIELD,
    PARK_FAILED,
    PARK_PUSH_FAILED,
    PR_NUMBER,
    RESET_COMMAND,
    FakePRRef,
    _patched,
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

# The receipt a landed publication leaves, both halves: the commit that
# reached the remote and the head it was pushed FROM, which is what dates it
# to the attempt this recovery is finishing.
KEY_PUBLISHED_SHA = "implementing_published_sha"
KEY_PUBLISHED_LEASE = "implementing_published_lease"

# What the attempt recorded about its own replay, dropped by the same write
# that drops the anchor beside it: the head it produced, and the publication
# it produced it for.
KEY_PENDING_REWRITE_SHA = "pending_auto_base_rebase_rewrite_sha"
KEY_PENDING_REWRITE_PR = "pending_auto_base_rebase_rewrite_pr"
KEY_PENDING_REWRITE_STAGE = "pending_auto_base_rebase_rewrite_stage"
KEY_ANNOUNCED_SHA = "pending_auto_base_rebase_announced_sha"

# A second open pull request on the same branch, for the case where the issue
# is repointed at one the interrupted rewrite was never made against.
REPOINTED_PR_NUMBER = 43

# The field a hand edit takes out of the identity group, leaving an exemption
# whose contribution nothing can name.
DAMAGED_IDENTITY_FIELD = "late_exempt_fingerprint"

# A lease no reader can hold to a commit, and one naming a head this attempt
# was never pinned to.
MALFORMED_LEASE = "not-a-commit"

# The pinned field an issue's own publication is recorded under, and what a
# client that cannot answer for the issue raises.
KEY_PR_NUMBER = "pr_number"

# The debt a grant writes beside the permission, in the one statement that
# makes each answer for the other.
KEY_APPROVED_SHA = "late_approved_sha"

# The three terms of an authorization a recovery cross-binds to the attempt it
# is finishing: the head the push was leased against, the pull request it was
# made for, and the base the replay was read over.
KEY_REWRITE_LEASE = "late_rewrite_lease"
KEY_REWRITE_PR = "late_rewrite_pr_number"
KEY_REWRITE_TO_BASE = "late_rewrite_to_base_sha"
GET_ISSUE = "get_issue"
UNREADABLE_ISSUE = "the issue could not be read again"

# The method and the stage the tick that really published recorded itself
# under, which is the one record a resumed finish may not add to.
CLEAN_REBASE = "auto_clean_rebase"
STAGE_FIELD = "stage"


class _ReadableOnce:
    """A client that answers for the issue once and refuses after that.

    The refresh reads the issue to find the worktree it is about, and the
    permit re-reads it before it will carry a human's verdict anywhere. Only
    the second read is what a case about an unconfirmable owner is seeding, so
    the first is left alone rather than the whole client being taken away.
    """

    def __init__(self, readable) -> None:
        self._readable = readable
        self._reads = itertools.count()

    def __call__(self, number: int):
        """Answer the tick's own read, and refuse every one behind it."""
        if next(self._reads):
            raise RuntimeError(UNREADABLE_ISSUE)
        return self._readable(number)


class _ResumedRebaseCase(_CleanRebaseCase):
    """One adjudicated rebase stopped mid-tick and resumed on the next one."""

    def setUp(self) -> None:
        super().setUp()
        adjudicated(self)

    def _assert_finished_the_route(self, method: str) -> None:
        """The anchor is gone, the round is reset, and review has the head."""
        self._assert_anchor(None)
        self.assertEqual(self._pinned()[KEY_REVIEW_ROUND], 0)
        self._assert_routed(True)
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

    def _issue(self):
        """The issue this fixture's whole world is about."""
        return self.gh._issues[ISSUE]

    def _edited(self, edit) -> None:
        """Apply one hand edit to the pinned comment, durably."""
        issue = self._issue()
        state = self.gh.read_pinned_state(issue)
        edit(state)
        self.gh.write_pinned_state(issue, state)

    def _assert_anchor(self, expected) -> None:
        """What the pinned comment says this attempt is still owed, if any."""
        self.assertEqual(self._pinned()[KEY_PENDING_PUSH_SHA], expected)

    def _assert_routed(self, routed: bool) -> None:
        """Whether the reviewer was sent back to the rewritten head."""
        self.assertEqual(
            (ISSUE, LABEL_VALIDATING) in self.gh.label_history, routed,
        )

    def _assert_parked(self, reason: str) -> None:
        """The reason a human is being asked to look at this issue."""
        self.assertEqual(self._pinned()[KEY_PARK_REASON], reason)

    def _assert_nothing_left(self, resumed) -> None:
        """No push went out on the road this tick could not finish."""
        resumed[PUSH_PATCH].assert_not_called()

    def _pinned(self) -> dict:
        """The pinned comment as the fake client stores it."""
        return self.gh.pinned_data(ISSUE)

    def _resets_of(self, resumed) -> list:
        """Every hard reset the hardened git seam was asked for this tick."""
        return [
            recorded for recorded in resumed[HARDENED_PATCH].call_args_list
            if recorded.args[:2] == (RESET_COMMAND, HARD_RESET_FLAG)
        ]

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
            self._pinned()[KEY_PARK_REASON], PARK_PUSH_FAILED,
        )

    def test_an_unreadable_permission_holds_the_route(self) -> None:
        # A group this build cannot read back whole is the only account there
        # is of how the exemption came to name what it names. Finishing the
        # route over it would clear the one anchor that brings this recovery
        # back, leaving the replay to be measured afresh, so the tick parks
        # with the record exactly as it stands.
        self._crashes_before_the_push()
        self._damages_the_permission()

        resumed = self._resumes(remote_head=AFTER_SHA)

        self._assert_nothing_left(resumed)
        self._assert_standing_permission()
        self._assert_held_for_a_human(resumed)

    def test_a_loose_checkout_holds_the_route(self) -> None:
        # A contribution fingerprinted beside changes nobody committed is not
        # the one the pull request carries, so the settlement may not be
        # taken -- and the route may not be finished either, since the
        # exemption is still on the commit the adjudication accepted.
        self._crashes_before_the_push()

        resumed = self._resumes(remote_head=AFTER_SHA, dirty=LOOSE_EDITS)

        self._assert_nothing_left(resumed)
        self._assert_standing_permission()
        self._assert_held_for_a_human(resumed)

    def test_a_refused_no_op_parks_in_place(self) -> None:
        # The pull request was standing on the replay when this tick read it
        # and refused the lease a moment later, so the remote moved in
        # between. The checkout is on the commit the pull request was
        # carrying, so nothing is reset off it and the anchor stays pinned for
        # the next tick to classify the remote afresh.
        self._crashes_before_the_push()

        resumed = self._resumes(remote_head=AFTER_SHA, push=False)

        self._assert_anchor(BEFORE_SHA)
        self._assert_parked(PARK_PUSH_FAILED)
        self.assertEqual(self._resets_of(resumed), [])
        self.assertEqual(self._events_of(EVENT_TRANSFER), [])

    def test_a_landed_rewrite_nothing_explains_holds(self) -> None:
        # The replay is on the pull request and the comment says nothing at
        # all about it -- no permission, no receipt. Finishing the route would
        # clear the anchor over an exemption still naming the commit the
        # adjudication accepted, so the next tick would measure the replay as
        # a fresh candidate.
        self._crashes_before_the_grant()

        resumed = self._resumes(remote_head=AFTER_SHA)

        self._assert_nothing_left(resumed)
        durable = self._durable()
        self.assertTrue(_exemption.is_exempt(durable, BEFORE_SHA))
        self.assertFalse(_rewrites.carries_rewrite_authorization(durable))
        self.assertEqual(self._events_of(EVENT_TRANSFER), [])
        self._assert_held_for_a_human(resumed)

    def test_a_settled_transfer_with_no_receipt_holds(self) -> None:
        # The rotation and the receipt go down in one write, so a comment
        # claiming the first without the second is one that did not land
        # whole -- and this tick may not decide which half is true.
        self._crashes_before_the_route()
        self._forgets_the_receipt()

        resumed = self._resumes(remote_head=AFTER_SHA)

        self._assert_nothing_left(resumed)
        self._assert_held_for_a_human(resumed)

    def test_a_partial_identity_holds_a_landing(self) -> None:
        # The exemption is real and what it contributes is not readable, so
        # the fail-closed readers answer "no identity" -- the same answer an
        # issue that never earned a verdict gives. Finishing the route on it
        # would drop the anchor with the verdict still on the old commit.
        self._crashes_before_the_grant()
        self._damages_the_identity()

        resumed = self._resumes(remote_head=AFTER_SHA)

        self._assert_nothing_left(resumed)
        self._assert_held_for_a_human(resumed)

    def test_a_partial_identity_resets_a_replay(self) -> None:
        # The same damage on the road where nothing has been pushed yet. Left
        # to the ordinary gate the replay is measured past the same ceiling
        # and adjudicated again, so the branch goes back onto the anchor and
        # a human is asked about the record instead.
        self._crashes_before_the_grant()
        self._damages_the_identity()

        resumed = self._resumes()

        self._assert_nothing_left(resumed)
        self._assert_reset_and_parked(resumed)

    def test_a_damaged_permission_resets_a_replay(self) -> None:
        # A transfer group this build cannot read whole, over a branch the
        # crash left rebased and unpushed. The permit refuses it, so the only
        # road left is the measurement -- which is the one answer an
        # adjudicated change may not get.
        self._crashes_before_the_push()
        self._damages_the_permission()

        resumed = self._resumes()

        self._assert_nothing_left(resumed)
        self._assert_reset_and_parked(resumed)

    def test_a_receipt_with_no_lease_holds(self) -> None:
        # A receipt is never cleared, so the commit it names on its own
        # vouches for any pull request somebody rewound onto it.
        self._assert_undatable_receipt_holds(None)

    def test_a_malformed_receipt_lease_holds(self) -> None:
        # A value that is not a commit dates the receipt to nothing, and the
        # reader may not fall back to the half it can still read.
        self._assert_undatable_receipt_holds(MALFORMED_LEASE)

    def test_a_mismatched_receipt_lease_holds(self) -> None:
        # A whole commit that is not the anchor this recovery holds records a
        # push made from some other attempt.
        self._assert_undatable_receipt_holds(FOREIGN_SHA)

    def _damages_the_permission(self) -> None:
        """Take one field out of the group the grant left on the comment."""
        issue = self._issue()
        state = self.gh.read_pinned_state(issue)
        state.data.pop(DAMAGED_FIELD)
        self.gh.write_pinned_state(issue, state)

    def _assert_undatable_receipt_holds(self, lease) -> None:
        """A settled transfer whose receipt this attempt cannot date holds."""
        self._crashes_before_the_route()
        self._repoints_the_receipt(lease)

        resumed = self._resumes(remote_head=AFTER_SHA)

        self._assert_nothing_left(resumed)
        self._assert_held_for_a_human(resumed)

    def _damages_the_identity(self) -> None:
        """Take one field out of the record of what the exempt commit adds."""
        self._edited(lambda state: state.data.pop(DAMAGED_IDENTITY_FIELD))

    def _repoints_the_receipt(self, lease) -> None:
        """Leave the receipt naming a head this attempt was not pushed from."""
        self._edited(lambda state: state.set(KEY_PUBLISHED_LEASE, lease))

    def _assert_reset_and_parked(self, resumed) -> None:
        """The branch is back on the anchor and a human owns the record."""
        self.assertEqual(len(self._resets_of(resumed)), 1)
        self._assert_nothing_readjudicated()
        self.assertEqual(self._events_of(EVENT_BASE_REBASED), [])
        self._assert_anchor(None)
        pinned = self._pinned()
        self.assertIsNone(pinned[KEY_PENDING_REWRITE_SHA])
        self.assertEqual(pinned[KEY_PARK_REASON], PARK_FAILED)
        self._assert_routed(False)

    def _assert_standing_permission(self) -> None:
        """The verdict is where the adjudication put it, and the claim stands."""
        durable = self._durable()
        self.assertTrue(_exemption.is_exempt(durable, BEFORE_SHA))
        self.assertTrue(_rewrites.carries_rewrite_authorization(durable))
        self.assertEqual(self._events_of(EVENT_TRANSFER), [])

    def _forgets_the_receipt(self) -> None:
        """Take the record of what reached the remote off the comment."""
        issue = self._issue()
        state = self.gh.read_pinned_state(issue)
        state.set(KEY_PUBLISHED_SHA, None)
        self.gh.write_pinned_state(issue, state)

    def _assert_held_for_a_human(self, resumed) -> None:
        """The anchor stands, HEAD is where it was, and nothing was reported.

        The remote carries the replay, so nothing is reset off it -- the park
        is what a route this tick could not finish owes, and the anchor left
        pinned is what lets the next one classify the remote afresh.
        """
        self._assert_nothing_readjudicated()
        self.assertEqual(self._events_of(EVENT_BASE_REBASED), [])
        self.assertEqual(self._resets_of(resumed), [])
        self._assert_anchor(BEFORE_SHA)
        self._assert_parked(PARK_PUSH_FAILED)
        self._assert_routed(False)


if __name__ == "__main__":
    unittest.main()


class RolledBackRemoteTest(_ResumedRebaseCase, unittest.TestCase):
    """The remote somebody put back after this attempt's push had landed."""

    def setUp(self) -> None:
        super().setUp()
        self._crashes_before_the_route()
        # The pull request is back on the head the rebase found it on, which
        # is the very commit a reissued push would lease itself against.
        self.resumed = self._resumes(remote_head=BEFORE_SHA, diverged=(1, 1))

    def test_nothing_is_pushed_over_the_rollback(self) -> None:
        self.resumed[PUSH_PATCH].assert_not_called()
        self.assertEqual(self._events_of(EVENT_BASE_REBASED), [])
        self._assert_routed(False)

    def test_the_branch_goes_back_where_the_remote_is(self) -> None:
        # The externally moved remote's own answer: HEAD onto the anchor the
        # pull request is standing on, the anchor dropped with it, and a human
        # asked which of the two heads the branch is supposed to be on.
        self.assertEqual(len(self._resets_of(self.resumed)), 1)
        pinned = self._pinned()
        self.assertIsNone(pinned[KEY_PENDING_PUSH_SHA])
        self.assertEqual(pinned[KEY_PARK_REASON], PARK_PUSH_FAILED)

    def test_the_settled_verdict_is_left_alone(self) -> None:
        # The transfer is over: the write that receipted it moved the
        # exemption, and a rollback nobody here made is not this recovery's
        # to undo.
        durable = self._durable()
        self.assertTrue(_exemption.is_exempt(durable, AFTER_SHA))
        self.assertEqual(
            _rewrites.read_rewrite_authorization(durable).phase,
            _rewrites.LateRewritePhase.PUBLISHED,
        )
        self.assertEqual(len(self._events_of(EVENT_TRANSFER)), 1)


class UnprovenLandingTest(_ResumedRebaseCase, unittest.TestCase):
    """A remote and a checkout that agree on a commit nothing recorded."""

    def test_a_mismatched_record_holds_the_route(self) -> None:
        # Both refs moved together while the pending record still names the
        # replay this attempt made. They agreeing proves only that they agree.
        self._crashes_before_the_route()
        self._repoints_the_rewrite(FOREIGN_SHA)

        resumed = self._resumes(remote_head=AFTER_SHA)

        self._assert_nothing_left(resumed)
        self._assert_held_for_a_human(resumed)

    def test_a_malformed_record_holds_the_route(self) -> None:
        # A pull request number no reader can hold to an identity leaves the
        # record unreadable as a whole, and an unreadable record vouches for
        # no publication at all.
        self._crashes_before_the_route()
        self._edited(lambda state: state.set(KEY_PENDING_REWRITE_PR, "forty"))

        resumed = self._resumes(remote_head=AFTER_SHA)

        self._assert_nothing_left(resumed)
        self._assert_held_for_a_human(resumed)

    def _repoints_the_rewrite(self, sha: str) -> None:
        """Leave the pending record naming a replay this attempt never made."""
        self._edited(lambda state: state.set(KEY_PENDING_REWRITE_SHA, sha))

    def _assert_held_for_a_human(self, resumed) -> None:
        """The anchor stands, HEAD is where it was, and the route is unfinished."""
        self.assertEqual(self._events_of(EVENT_BASE_REBASED), [])
        self._assert_anchor(BEFORE_SHA)
        self._assert_parked(PARK_PUSH_FAILED)
        self._assert_routed(False)


class RefusedSettlementTest(_ResumedRebaseCase, unittest.TestCase):
    """The permit is the whole of what may settle a landed rewrite."""

    def test_a_relabelled_issue_refuses(self) -> None:
        # The rewrite was entered from the stage the record names, and a
        # publication made under one stage may not be settled under another.
        self._crashes_before_the_push()
        self.gh.set_workflow_label(
            self._issue(), WorkflowLabel.DOCUMENTING,
        )

        self._assert_refuses()

    def test_a_repointed_publication_refuses(self) -> None:
        # The issue now records some other pull request, so the permission on
        # the comment describes a publication this call is not entered on.
        self._crashes_before_the_push()
        self._repoints_the_pull_request()

        self._assert_refuses()

    def test_an_unreadable_owner_refuses(self) -> None:
        # A transfer carries a human's verdict forward without re-asking a
        # human anything, so the issue is re-read for it -- and a read that
        # established nothing settles nothing.
        self._crashes_before_the_push()
        self._unreadable_after_the_tick_opens()

        self._assert_refuses()

    def test_an_unheld_lease_refuses(self) -> None:
        # The head the push was leased against is the one end nothing else
        # here reads as an object, and an id this host cannot peel is evidence
        # nobody can check.
        self._crashes_before_the_push()
        self.reading.unheld.add(BEFORE_SHA)

        self._assert_refuses()

    def _repoints_the_pull_request(self) -> None:
        """Record a different open pull request on the same branch."""
        self._add_pr(
            pr_number=REPOINTED_PR_NUMBER,
            head=FakePRRef(sha=AFTER_SHA),
        )
        issue = self._issue()
        state = self.gh.read_pinned_state(issue)
        state.set(KEY_PR_NUMBER, REPOINTED_PR_NUMBER)
        self.gh.write_pinned_state(issue, state)

    def _unreadable_after_the_tick_opens(self) -> None:
        """Let the refresh find the issue and refuse every read behind it."""
        _patched(self, self.gh, GET_ISSUE, _ReadableOnce(self.gh.get_issue))

    def _assert_refuses(self) -> None:
        """Nothing is pushed, nothing rotates, and the route is unfinished."""
        resumed = self._resumes(remote_head=AFTER_SHA)

        self._assert_nothing_left(resumed)
        durable = self._durable()
        self.assertTrue(_exemption.is_exempt(durable, BEFORE_SHA))
        self.assertEqual(
            _rewrites.read_rewrite_authorization(durable).phase,
            _rewrites.LateRewritePhase.AUTHORIZED,
        )
        self.assertEqual(self._events_of(EVENT_TRANSFER), [])
        self._assert_nothing_readjudicated()
        self.assertEqual(self._events_of(EVENT_BASE_REBASED), [])
        self._assert_anchor(BEFORE_SHA)


class ForeignPublicationTest(_ResumedRebaseCase, unittest.TestCase):
    """An attempt made for a publication this issue no longer records."""

    def test_a_relabel_parks_an_unpushed_replay(self) -> None:
        # Every road out of a recovery posts a notice to the pull request this
        # tick holds and files its audit event under the stage this tick
        # reads. A relabel made while the process was down would have both
        # attributed to a publication the attempt was never made for.
        self._crashes_before_the_grant()
        self._relabels()

        resumed = self._resumes()

        self._assert_parked_in_place(resumed)
        self.assertEqual(self._events_of(EVENT_MEASUREMENT), [])

    def test_a_repoint_parks_a_landed_rewrite(self) -> None:
        # The same after the receipt has landed, which is the road that would
        # otherwise finalize: the transfer is settled and nothing is left to
        # push, so the only thing finishing buys is a notice and an event on
        # the wrong pull request -- and the anchor gone.
        self._crashes_before_the_route()
        self._repoints_the_pull_request()

        resumed = self._resumes(remote_head=AFTER_SHA)

        self._assert_parked_in_place(resumed)
        self.assertEqual(len(self._events_of(EVENT_TRANSFER)), 1)

    def test_the_evidence_names_the_recorded_terms(self) -> None:
        # The record is the source of the terms a re-derived rewrite is
        # decided on. Taken from the context instead they would compare today
        # with today, and the permit's publication checks would pass on any
        # repoint or relabel the crash window allowed.
        self._crashes_before_the_grant()

        rewrite = transfers._reconstructed(
            self._elsewhere(), AFTER_SHA, transfers._Handoff.UNRECORDED,
        )

        self.assertEqual(rewrite.pr_number, PR_NUMBER)
        self.assertEqual(rewrite.source_stage, WorkflowLabel.IN_REVIEW)

    def _relabels(self) -> None:
        """Move the issue to another stage the refresh also drives."""
        self.gh.set_workflow_label(
            self._issue(), WorkflowLabel.DOCUMENTING,
        )

    def _repoints_the_pull_request(self) -> None:
        """Record a different open pull request on the same branch."""
        self._add_pr(
            pr_number=REPOINTED_PR_NUMBER,
            head=FakePRRef(sha=AFTER_SHA),
        )
        issue = self._issue()
        state = self.gh.read_pinned_state(issue)
        state.set(KEY_PR_NUMBER, REPOINTED_PR_NUMBER)
        self.gh.write_pinned_state(issue, state)

    def _elsewhere(self) -> _AutoRebaseRecoveryContext:
        """The same recovery, on the publication a repoint moved it to."""
        durable = self._durable()
        return _AutoRebaseRecoveryContext(
            gh=self.gh,
            spec=self.spec,
            issue=self._issue(),
            state=durable,
            worktree=self.wt,
            pr_number=REPOINTED_PR_NUMBER,
            label=WorkflowLabel.DOCUMENTING,
            pending_pre_rebase_sha=BEFORE_SHA,
            pending_rewrite=transfers._pending_rewrite(durable),
        )

    def _assert_parked_in_place(self, resumed) -> None:
        """Nothing pushed, nothing reset, and the whole record still pinned."""
        self._assert_nothing_left(resumed)
        self.assertEqual(self._resets_of(resumed), [])
        self.assertEqual(self._events_of(EVENT_BASE_REBASED), [])
        self._assert_nothing_readjudicated()
        self._assert_anchor(BEFORE_SHA)
        pinned = self._pinned()
        self.assertEqual(pinned[KEY_PENDING_REWRITE_SHA], AFTER_SHA)
        self.assertEqual(pinned[KEY_PARK_REASON], PARK_FAILED)


class ForeignRelabelTest(_ResumedRebaseCase, unittest.TestCase):
    """A move to the stage this route ends on, made by somebody else."""

    def test_a_relabel_over_an_unpushed_replay_parks(self) -> None:
        # The label alone cannot say whose move it was, and the effect a
        # finish leaves is absent here: nothing was pushed, so the pull
        # request is still on the anchor and no receipt names the replay.
        # Taken for this route's own step, the tick would measure and publish
        # a checkout nothing vouched for.
        self._crashes_before_the_grant()
        self.gh.set_workflow_label(self._issue(), WorkflowLabel.VALIDATING)

        resumed = self._resumes()

        self._assert_nothing_left(resumed)
        self.assertEqual(self._resets_of(resumed), [])
        self.assertEqual(self._events_of(EVENT_MEASUREMENT), [])
        self._assert_anchor(BEFORE_SHA)
        self._assert_parked(PARK_FAILED)


class RefusedRetryTest(_ResumedRebaseCase, unittest.TestCase):
    """The permit is the whole of what may reissue an interrupted push."""

    def test_an_unheld_lease_resets_the_replay(self) -> None:
        # The head the push was leased against is not an object this host
        # holds, so the permission granted for the replay cannot be re-asked
        # on evidence anybody can check. Measured instead, the replay is
        # force-pushed and the recovery cleared with the verdict unmoved.
        self._crashes_before_the_push()
        self.reading.unheld.add(BEFORE_SHA)

        resumed = self._resumes()

        self._assert_nothing_left(resumed)
        self.assertEqual(len(self._resets_of(resumed)), 1)
        self.assertEqual(self._events_of(EVENT_TRANSFER), [])
        self._assert_nothing_readjudicated()
        self._assert_anchor(None)
        self._assert_parked(PARK_FAILED)
        self.assertTrue(_exemption.is_exempt(self._durable(), BEFORE_SHA))


class UnboundAuthorizationTest(_ResumedRebaseCase, unittest.TestCase):
    """A whole record whose terms belong to some other attempt."""

    def test_a_foreign_lease_holds_the_route(self) -> None:
        # The head the permit was granted against is not the anchor this
        # recovery is finishing, so the permission describes a push some
        # other attempt was going to make.
        self._assert_unbound(KEY_REWRITE_LEASE, FOREIGN_SHA)

    def test_a_foreign_publication_holds_the_route(self) -> None:
        # The pull request the rewrite was made against is not the one the
        # attempt recorded rebasing for.
        self._assert_unbound(KEY_REWRITE_PR, REPOINTED_PR_NUMBER)

    def test_a_foreign_replayed_base_holds_the_route(self) -> None:
        # The base the transfer says the replay sits over is not the one the
        # identity beside it records, so the pair the digest was taken
        # between is a contribution this issue never adjudicated.
        self._assert_unbound(KEY_REWRITE_TO_BASE, FOREIGN_SHA)

    def _assert_unbound(self, field: str, recorded) -> None:
        """One term moved off the attempt, and the hold it has to earn."""
        self._crashes_before_the_route()
        self._edited(lambda state: state.set(field, recorded))

        resumed = self._resumes(remote_head=AFTER_SHA)

        self._assert_nothing_left(resumed)
        self.assertEqual(self._events_of(EVENT_MEASUREMENT), [])
        self.assertEqual(self._events_of(EVENT_BASE_REBASED), [])
        self._assert_anchor(BEFORE_SHA)
        self._assert_parked(PARK_PUSH_FAILED)


class LooseSettledTreeTest(_ResumedRebaseCase, unittest.TestCase):
    """A settled handoff over a checkout carrying work nobody committed."""

    def test_a_dirty_settled_handoff_holds_the_route(self) -> None:
        # Finishing hands the issue to the reviewer, and a reviewer sent to a
        # checkout with uncommitted files reads work the pull request does not
        # have as though it were under review.
        self._crashes_before_the_route()

        resumed = self._resumes(remote_head=AFTER_SHA, dirty=LOOSE_EDITS)

        self._assert_nothing_left(resumed)
        self.assertEqual(self._resets_of(resumed), [])
        self.assertEqual(self._events_of(EVENT_BASE_REBASED), [])
        self._assert_routed(False)
        self._assert_anchor(BEFORE_SHA)
        self._assert_parked(PARK_PUSH_FAILED)


class UnroutedFinishTest(_ResumedRebaseCase, unittest.TestCase):
    """A finish that said what it published and never routed the reviewer."""

    def setUp(self) -> None:
        super().setUp()
        self._crashes_at_the_relabel()
        self.resumed = self._resumes(remote_head=AFTER_SHA)

    def test_the_reviewer_is_still_sent_to_the_replay(self) -> None:
        # The anchor is the only thing that brings this tick back, so clearing
        # it without the relabel would strand the issue on the stage the
        # rebase ran from with nothing left to correct it.
        self._assert_routed(True)
        self._assert_anchor(None)
        self.assertEqual(self._pinned()[KEY_REVIEW_ROUND], 0)

    def test_nothing_it_already_said_is_said_again(self) -> None:
        self._assert_nothing_left(self.resumed)
        self.assertEqual(
            [record[METHOD_FIELD] for record in self._events_of(
                EVENT_BASE_REBASED,
            )],
            [CLEAN_REBASE],
        )
        self.assertEqual(len(self._events_of(EVENT_TRANSFER)), 1)


class UndoneAttemptTest(_ResumedRebaseCase, unittest.TestCase):
    """A branch put back on the anchor with the attempt's records standing."""

    def test_an_undone_replay_parks_and_rolls_back(self) -> None:
        # HEAD is exactly where the attempt anchored it and the comment still
        # carries the replay it recorded and the permission granted for it.
        # Read as an attempt that never started, the anchor would be dropped,
        # the transfer state left for the next grant to trip over, and the
        # branch handed straight to a fresh rebase.
        self._crashes_before_the_push()

        resumed = self._resumes(local_head=BEFORE_SHA)

        self._assert_nothing_left(resumed)
        self.assertEqual(len(self._resets_of(resumed)), 1)
        self.assertEqual(self._events_of(EVENT_MEASUREMENT), [])
        self._assert_routed(False)
        self._assert_anchor(None)
        self._assert_parked(PARK_FAILED)

    def test_the_rollback_it_abandoned_is_finished(self) -> None:
        # The reset that put the branch back owed two drops and made neither:
        # the debt for a commit no branch has, and the permission that will
        # never be spent on it. The exemption is untouched, since the grant
        # never moved it.
        self._crashes_before_the_push()

        self._resumes(local_head=BEFORE_SHA)

        durable = self._durable()
        self.assertTrue(_exemption.is_exempt(durable, BEFORE_SHA))
        self.assertFalse(_rewrites.carries_rewrite_authorization(durable))
        self.assertIsNone(self._pinned()[KEY_APPROVED_SHA])
        self.assertIsNone(self._pinned()[KEY_PENDING_REWRITE_SHA])


class DamagedAttemptRecordTest(_ResumedRebaseCase, unittest.TestCase):
    """A record of the attempt that claims more than it can show."""

    def test_a_partial_record_resets_the_replay(self) -> None:
        # The remote is on the anchor and the checkout is ahead of it, which
        # is the shape the ahead-only fallback publishes. Read as the absence
        # it resembles, a group something took a member out of would send the
        # replay to the ordinary gate and force-push whatever came back.
        self._assert_resets_the_replay(None)

    def test_a_malformed_head_resets_the_replay(self) -> None:
        # A value that is not a whole git object id is not a commit this tick
        # can compare anything to. Accepted for being a string, it would name
        # a checkout nothing here ever wrote and reach the same push.
        self._assert_resets_the_replay(MALFORMED_LEASE)

    def test_a_malformed_head_is_no_record(self) -> None:
        # Read one step earlier than the park: a value that is not a whole git
        # object id is not a commit anything can be compared to, so the group
        # is damaged rather than one naming a head the checkout might turn out
        # to be standing on.
        self._crashes_before_the_grant()
        self._edited(
            lambda state: state.set(KEY_PENDING_REWRITE_SHA, MALFORMED_LEASE),
        )

        recorded = transfers._pending_rewrite(self._durable())

        self.assertFalse(recorded.is_recorded)
        self.assertTrue(recorded.is_damaged)

    def test_another_commit_resets_the_replay(self) -> None:
        # The record is whole and vouches for some other head, which is the
        # attempt's own answer that this checkout is not its work. Only a
        # comment carrying none of the group reaches the counts.
        self._assert_resets_the_replay(FOREIGN_SHA)

    def _assert_resets_the_replay(self, recorded) -> None:
        """One hand-edited head, and the reset-and-park it has to earn."""
        self._crashes_before_the_grant()
        self._edited(
            lambda state: state.set(KEY_PENDING_REWRITE_SHA, recorded),
        )

        resumed = self._resumes()

        self._assert_nothing_left(resumed)
        self.assertEqual(len(self._resets_of(resumed)), 1)
        self.assertEqual(self._events_of(EVENT_MEASUREMENT), [])
        self._assert_nothing_readjudicated()
        self._assert_anchor(None)
        self._assert_parked(PARK_FAILED)


class RelabelledFinishTest(_ResumedRebaseCase, unittest.TestCase):
    """The route this recovery's own finish had already most of the way made."""

    def setUp(self) -> None:
        super().setUp()
        self._crashes_after_the_relabel()
        self.crashed = dict(self._pinned())
        self.resumed = self._resumes(remote_head=AFTER_SHA)

    def test_the_crash_left_the_route_half_made(self) -> None:
        # The premise: the reviewer has been routed at the rewritten head, the
        # finish has recorded that it said so, and the write that clears the
        # attempt never happened.
        self._assert_routed(True)
        self.assertEqual(self.crashed[KEY_ANNOUNCED_SHA], AFTER_SHA)
        self.assertEqual(self.crashed[KEY_PENDING_PUSH_SHA], BEFORE_SHA)

    def test_the_next_tick_writes_rather_than_parks(self) -> None:
        # The relabel is this route's own last step before the write that
        # clears the record. Read as somebody else's move, the tick with only
        # that write left to make would park for a human forever.
        self._assert_nothing_left(self.resumed)
        self._assert_anchor(None)
        self.assertEqual(self._pinned()[KEY_REVIEW_ROUND], 0)
        self.assertEqual(self._events_of(EVENT_MEASUREMENT), [])

    def test_the_finish_it_made_is_not_made_again(self) -> None:
        # The notice, the audit event, and the route all went out before the
        # write the crash swallowed, so the tick that makes that write owes
        # none of them -- a second `base_rebased` would be filed under the
        # stage the relabel moved to, for one publication that happened once.
        rebased = self._events_of(EVENT_BASE_REBASED)

        self.assertEqual([record[METHOD_FIELD] for record in rebased],
                         [CLEAN_REBASE])
        self.assertEqual(rebased[0][STAGE_FIELD], LABEL)
        self.assertEqual(len(self._pr_comments()), 1)

    def test_the_settled_verdict_is_reported_once(self) -> None:
        self._assert_settled_once()

    def _pr_comments(self) -> list:
        """Every comment this journey posted on the pull request."""
        return list(self.gh.posted_pr_comments)


class UnpairedPermissionTest(_ResumedRebaseCase, unittest.TestCase):
    """A permission whose debt was written with it and is not there now."""

    def test_a_damaged_identity_resets_the_replay(self) -> None:
        # The permission still reads back whole, and what it is a claim about
        # -- the verdict and the contribution under it -- no longer does.
        # Believed, the settlement re-asks a permit whose accepted pair cannot
        # be fingerprinted, the ordinary gate measures the replay instead, and
        # a change a human already ruled on is published and announced.
        self._crashes_before_the_push()
        self._edited(lambda state: state.data.pop(DAMAGED_IDENTITY_FIELD))

        resumed = self._resumes()

        self._assert_nothing_left(resumed)
        self.assertEqual(len(self._resets_of(resumed)), 1)
        self.assertEqual(self._events_of(EVENT_MEASUREMENT), [])
        self.assertEqual(self._events_of(EVENT_TRANSFER), [])
        self._assert_nothing_readjudicated()
        self._assert_routed(False)
        self._assert_parked(PARK_FAILED)

    def test_an_unpaired_permission_resets_the_replay(self) -> None:
        # The grant writes the permission and the debt in one statement for
        # one commit. Read as outstanding, the settlement re-asks the permit
        # -- and a permit that grants re-writes BOTH, so the missing half
        # would be reconstructed from the very claim nobody could check and
        # the push would go out under it.
        self._crashes_before_the_push()
        self._edited(lambda state: state.set(KEY_APPROVED_SHA, None))

        resumed = self._resumes()

        self._assert_nothing_left(resumed)
        self.assertEqual(len(self._resets_of(resumed)), 1)
        self.assertEqual(self._events_of(EVENT_MEASUREMENT), [])
        self.assertEqual(self._events_of(EVENT_TRANSFER), [])
        self._assert_nothing_readjudicated()
        self._assert_parked(PARK_FAILED)

    def test_a_repointed_debt_resets_the_replay(self) -> None:
        # The same disagreement one field over: a debt owed for a commit this
        # permission was never granted for. Its lease still names the anchor,
        # so the refresh is not frozen out and the recovery has to answer.
        self._crashes_before_the_push()
        self._edited(lambda state: state.set(KEY_APPROVED_SHA, FOREIGN_SHA))

        resumed = self._resumes()

        self._assert_nothing_left(resumed)
        self.assertEqual(len(self._resets_of(resumed)), 1)
        self.assertEqual(self._events_of(EVENT_TRANSFER), [])
        self._assert_parked(PARK_FAILED)
