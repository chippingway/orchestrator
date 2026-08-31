# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a silent `validating` recovery is allowed to put on its pull request.

Both transient parks that touch git end in a push onto a pull request the
remote already carries, and neither has a run behind it to have measured what
that push would take the pull request to. So they go through the same
cumulative gate every other fix does: the deferred push republishes a commit
the gate already ruled on, and the commit a timeout stranded is measured
before it joins anything.

The refusals are the point as much as the publications. A pull request nobody
can push onto, one somebody moved under the park, and a checkout that moved
between the recovery's own read and the gate's proof each leave the park where
it stands -- and a candidate the reading finds too big is handed to the
adjudication rather than pushed, with the round it spent counted inside the
gate's own write.
"""
from __future__ import annotations

import unittest

from tests.workflow.stages.validating import recovered_gate_support as support

AWAITING_HUMAN = support.AWAITING_HUMAN
CEILING = support.CEILING
COUNT_ADDED_LINES = support.COUNT_ADDED_LINES
KEY_ADDITIONS = support.KEY_ADDITIONS
KEY_APPROVED_LEASE = support.KEY_APPROVED_LEASE
KEY_APPROVED_SHA = support.KEY_APPROVED_SHA
KEY_BASE_SHA = support.KEY_BASE_SHA
KEY_CANDIDATE_SHA = support.KEY_CANDIDATE_SHA
KEY_PUBLISHED_SHA = support.KEY_PUBLISHED_SHA
KEY_RECEIPT_LEASE = support.KEY_RECEIPT_LEASE
KEY_RECEIPT_SHA = support.KEY_RECEIPT_SHA
KEY_SOURCE_STAGE = support.KEY_SOURCE_STAGE
LABEL_DECOMPOSING = support.LABEL_DECOMPOSING
LABEL_VALIDATING = support.LABEL_VALIDATING
LEASE = support.LEASE
MAX_ADDED_LINES = support.MAX_ADDED_LINES
MEASURED_BASE_SHA = support.MEASURED_BASE_SHA
MOVED_HEAD = support.MOVED_HEAD
MOVED_MID_TICK = support.MOVED_MID_TICK
PARK_AGENT_TIMEOUT = support.PARK_AGENT_TIMEOUT
PARK_MEASUREMENT_FAILED = support.PARK_MEASUREMENT_FAILED
PARK_PUSH_FAILED = support.PARK_PUSH_FAILED
PARK_REASON = support.PARK_REASON
PAST_THE_CEILING = support.PAST_THE_CEILING
PRE_DEV_FIX_SHA = support.PRE_DEV_FIX_SHA
PUBLICATION_HEAD = support.PUBLICATION_HEAD
PUSH_BRANCH = support.PUSH_BRANCH
RECOVERY_ISSUE = support.RECOVERY_ISSUE
RECOVERY_PR = support.RECOVERY_PR
REVIEW_ROUND = support.REVIEW_ROUND
REVISION = support.REVISION
RUN_AGENT = support.RUN_AGENT
STRANDED_CANDIDATE = support.STRANDED_CANDIDATE
UNDER_THE_CEILING = support.UNDER_THE_CEILING
FrozenCommit = support.FrozenCommit
PUSH_RETRIED_DETAIL = support.PUSH_RETRIED_DETAIL
TIMEOUT_EMPTY_DETAIL = support.TIMEOUT_EMPTY_DETAIL
TIMEOUT_PUSHED_DETAIL = support.TIMEOUT_PUSHED_DETAIL
config = support.config
patch = support.patch

# The round the fixture parks on, and the one a published recovery moves it to.
PARKED_ROUND = 1
SPENT_ROUND = 2


class DeferredPushRecoveryTest(
    unittest.TestCase, support._RecoveredPublicationMixin,
):
    """The push a `push_failed` park deferred, retried through the gate."""

    def test_an_approved_commit_is_unmeasured(self) -> None:
        # A reading already settled this commit, so the retry is the push that
        # reading licensed and nothing else: no agent, no second count, and
        # the two commits the push is named and pinned by come off the
        # approval rather than off whatever the remote says now.
        scenario = self._seed_deferred_push()

        mocks = self._recover(scenario)

        mocks[RUN_AGENT].assert_not_called()
        mocks[COUNT_ADDED_LINES].assert_not_called()
        pushed = self._assert_pushed_once(mocks)
        self.assertEqual(pushed.kwargs[REVISION], STRANDED_CANDIDATE)
        self.assertEqual(pushed.kwargs[LEASE], PUBLICATION_HEAD)

    def test_a_landed_push_settles_the_debt_it_paid(self) -> None:
        # The approval says one commit is still owed a publication, and left
        # standing past the push that made it, it freezes this branch out of
        # the pre-tick base refresh for the rest of the issue's life. The
        # receipt beside it is what names the commit that reached the remote.
        scenario = self._seed_deferred_push()

        self._recover(scenario)

        pinned = self._pinned(scenario)
        self.assertIsNone(pinned[KEY_APPROVED_SHA])
        self.assertIsNone(pinned[KEY_APPROVED_LEASE])
        self.assertEqual(pinned[KEY_RECEIPT_SHA], STRANDED_CANDIDATE)
        self.assertEqual(pinned[KEY_RECEIPT_LEASE], PUBLICATION_HEAD)

    def test_a_healed_park_counts_one_round(self) -> None:
        # The head the reviewer rejected is superseded, so the round is spent
        # exactly as a dev run's own push spends one -- and the mention the
        # park left is retired rather than being the thread's last word.
        scenario = self._seed_deferred_push()

        self._recover(scenario)

        self.assertEqual(self._pinned(scenario)[REVIEW_ROUND], SPENT_ROUND)
        self._assert_park_cleared(scenario)
        self._assert_recovery_followup(scenario.github, PUSH_RETRIED_DETAIL)

    def test_a_push_that_misses_leaves_it_owed(self) -> None:
        # Somebody pushed to the pull request while the issue sat parked, so
        # the lease the approval records refuses. Nothing may be dropped on
        # that answer: the commit is still owed a publication, the round it
        # would spend is unspent, and the park is what brings the next tick
        # back for it.
        scenario = self._seed_deferred_push()
        scenario.github.get_pr(RECOVERY_PR).head.sha = MOVED_HEAD

        mocks = self._recover(scenario, push_branch=False)

        self._assert_pushed_once(mocks)
        pinned = self._pinned(scenario)
        self.assertEqual(pinned[KEY_APPROVED_SHA], STRANDED_CANDIDATE)
        self.assertEqual(pinned[KEY_APPROVED_LEASE], PUBLICATION_HEAD)
        self.assertEqual(pinned[REVIEW_ROUND], PARKED_ROUND)
        self._assert_park_stands(scenario, PARK_PUSH_FAILED)

    def test_a_closed_pull_request_refuses_the_retry(self) -> None:
        # A closed pull request has nowhere for the push to land, so the entry
        # refuses and the gate parks on its own reason. The caller announces
        # no recovery and moves no label: it would be saying a park healed
        # that the gate has just replaced.
        scenario = self._seed_deferred_push()
        scenario.github.get_pr(RECOVERY_PR).state = "closed"

        mocks = self._recover(scenario)

        mocks[PUSH_BRANCH].assert_not_called()
        pinned = self._pinned(scenario)
        self.assertTrue(pinned[AWAITING_HUMAN])
        self.assertEqual(pinned[PARK_REASON], PARK_MEASUREMENT_FAILED)
        self.assertEqual(pinned[REVIEW_ROUND], PARKED_ROUND)
        self.assertEqual(scenario.github.label_history, [])

    def test_a_crashed_tick_counts_no_round(self) -> None:
        # The push landed and the write carrying its receipt went down with
        # it; what died was the clear behind them, so the park is still up.
        # The retry finds the pull request standing on the commit, so its
        # push is the leased no-op that proves as much -- and the round the
        # tick that really published it counted is not counted again.
        scenario = self._seed_deferred_push(**{
            KEY_APPROVED_SHA: None,
            KEY_APPROVED_LEASE: None,
            KEY_RECEIPT_SHA: STRANDED_CANDIDATE,
            KEY_RECEIPT_LEASE: PUBLICATION_HEAD,
            REVIEW_ROUND: SPENT_ROUND,
        })
        scenario.github.get_pr(RECOVERY_PR).head.sha = STRANDED_CANDIDATE

        mocks = self._recover(scenario)

        mocks[COUNT_ADDED_LINES].assert_not_called()
        pushed = self._assert_pushed_once(mocks)
        self.assertEqual(pushed.kwargs[REVISION], STRANDED_CANDIDATE)
        self.assertEqual(pushed.kwargs[LEASE], STRANDED_CANDIDATE)
        self.assertEqual(self._pinned(scenario)[REVIEW_ROUND], SPENT_ROUND)
        self._assert_park_cleared(scenario)


class TimedOutFixRecoveryTest(
    unittest.TestCase, support._RecoveredPublicationMixin,
):
    """The commit a killed run made, measured before it joins anything."""

    def test_a_stranded_commit_is_measured_first(self) -> None:
        # The one road to a published pull request that never reached the
        # gate: nothing measured what the killed run committed. The reading is
        # cumulative -- taken from the base the REMOTE names to the checkout's
        # head, so it covers everything the pull request comes to rather than
        # the diff of whatever the run got as far as committing.
        scenario = self._seed_timed_out()

        mocks = self._recover(scenario, added_lines=UNDER_THE_CEILING)

        mocks[RUN_AGENT].assert_not_called()
        mocks[COUNT_ADDED_LINES].assert_called_once()
        self.assertEqual(
            mocks[COUNT_ADDED_LINES].call_args.args[1:],
            (MEASURED_BASE_SHA, STRANDED_CANDIDATE),
        )
        pushed = self._assert_pushed_once(mocks)
        self.assertEqual(pushed.kwargs[REVISION], STRANDED_CANDIDATE)
        self.assertEqual(pushed.kwargs[LEASE], PUBLICATION_HEAD)

    def test_a_published_recovery_closes_the_park(self) -> None:
        # The anchor the park stamped has been answered, so leaving it would
        # let a later tick compare a fresh head against a head from rounds
        # ago. The round and the follow-up are the rest of what the landed
        # push earns.
        scenario = self._seed_timed_out()

        self._recover(scenario, added_lines=UNDER_THE_CEILING)

        pinned = self._pinned(scenario)
        self.assertIsNone(pinned[PRE_DEV_FIX_SHA])
        self.assertEqual(pinned[KEY_RECEIPT_SHA], STRANDED_CANDIDATE)
        self.assertEqual(pinned[REVIEW_ROUND], SPENT_ROUND)
        self._assert_park_cleared(scenario)
        self._assert_recovery_followup(scenario.github, TIMEOUT_PUSHED_DETAIL)

    def test_an_empty_run_is_never_measured(self) -> None:
        # The checkout is where the killed run found it, so there is nothing
        # to publish and nothing to read the size of. The park clears all the
        # same -- the reviewer is what the issue needs next -- and the
        # follow-up says which of the two things happened.
        scenario = self._seed_timed_out(**{
            PRE_DEV_FIX_SHA: STRANDED_CANDIDATE,
        })

        mocks = self._recover(scenario)

        mocks[COUNT_ADDED_LINES].assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()
        pinned = self._pinned(scenario)
        self.assertIsNone(pinned[PRE_DEV_FIX_SHA])
        self.assertEqual(pinned[REVIEW_ROUND], PARKED_ROUND)
        self._assert_park_cleared(scenario)
        self._assert_recovery_followup(scenario.github, TIMEOUT_EMPTY_DETAIL)

    def test_a_moved_pull_request_refuses(self) -> None:
        # The head the killed run began at is the head its pull request was
        # standing on, and naming it is what makes somebody else's push refuse
        # rather than be adopted as the lease. The two readings disagree, so
        # nothing is measured, nothing is pushed, and the park stands.
        scenario = self._seed_timed_out()
        scenario.github.get_pr(RECOVERY_PR).head.sha = MOVED_HEAD

        mocks = self._recover(scenario, added_lines=UNDER_THE_CEILING)

        mocks[COUNT_ADDED_LINES].assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()
        pinned = self._pinned(scenario)
        self.assertEqual(pinned[PRE_DEV_FIX_SHA], PUBLICATION_HEAD)
        self.assertEqual(pinned[REVIEW_ROUND], PARKED_ROUND)
        self.assertEqual(pinned[PARK_REASON], PARK_MEASUREMENT_FAILED)

    def test_a_checkout_that_moved_is_refused(self) -> None:
        # The recovery reads the head to decide there is anything to publish,
        # and the gate proves the checkout again behind it. A commit landing
        # in that window would otherwise be measured, pushed, and receipted as
        # the work the killed run left, so the two readings are one decision.
        scenario = self._seed_timed_out()

        mocks = self._recover(
            scenario,
            head_shas=(STRANDED_CANDIDATE,),
            candidate_commit=(FrozenCommit(sha=MOVED_MID_TICK),) * 4,
        )

        mocks[COUNT_ADDED_LINES].assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()
        pinned = self._pinned(scenario)
        self.assertEqual(pinned[PRE_DEV_FIX_SHA], PUBLICATION_HEAD)
        self.assertEqual(pinned[PARK_REASON], PARK_MEASUREMENT_FAILED)

    def test_a_retry_counts_one_round(self) -> None:
        # The first attempt measures the candidate and cannot land it, so what
        # it leaves is an approval and the round that reading owed. The second
        # publishes from there without measuring again, and the round the
        # first attempt froze is spent once rather than recomputed per poll.
        scenario = self._seed_timed_out()

        missed = self._recover(
            scenario, added_lines=UNDER_THE_CEILING, push_branch=False,
        )
        self.assertEqual(self._pinned(scenario)[REVIEW_ROUND], PARKED_ROUND)
        self._assert_park_stands(scenario, PARK_AGENT_TIMEOUT)

        landed = self._recover(scenario, added_lines=UNDER_THE_CEILING)

        missed[COUNT_ADDED_LINES].assert_called_once()
        landed[COUNT_ADDED_LINES].assert_not_called()
        self.assertEqual(self._pinned(scenario)[REVIEW_ROUND], SPENT_ROUND)
        self._assert_park_cleared(scenario)

    def test_an_oversized_accumulation_is_held(self) -> None:
        # What the killed run committed is measured as everything the pull
        # request comes to with it, so a run that got several commits in meets
        # the ceiling on their total. Past it, nothing is pushed, the issue
        # goes to the adjudication instead of back to the reviewer, and the
        # round it spent is counted inside the gate's own write -- ahead of
        # the label it moves, since no tick after this one would go back for
        # it.
        scenario = self._seed_timed_out()

        with patch.object(config, MAX_ADDED_LINES, CEILING):
            mocks = self._recover(scenario, added_lines=PAST_THE_CEILING)

        mocks[PUSH_BRANCH].assert_not_called()
        pinned = self._pinned(scenario)
        self.assertEqual(pinned[KEY_ADDITIONS], PAST_THE_CEILING)
        self.assertEqual(pinned[KEY_BASE_SHA], MEASURED_BASE_SHA)
        self.assertEqual(pinned[KEY_CANDIDATE_SHA], STRANDED_CANDIDATE)
        self.assertEqual(pinned[KEY_PUBLISHED_SHA], PUBLICATION_HEAD)
        self.assertEqual(pinned[KEY_SOURCE_STAGE], LABEL_VALIDATING)
        self.assertEqual(pinned[REVIEW_ROUND], SPENT_ROUND)
        self.assertEqual(
            scenario.github.label_history,
            [(RECOVERY_ISSUE, LABEL_DECOMPOSING)],
        )
        self._assert_nothing_healed(scenario)


if __name__ == "__main__":
    unittest.main()
