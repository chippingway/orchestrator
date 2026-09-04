# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the gate measures once a pull request already carries the work.

The count is what the pull request COMES TO rather than what the last commit
changed, the ceiling is passed strictly, a candidate at or below it joins the
pull request named and leased by what the gate froze, one past it is held with
the pull request left exactly where it stood, and `DECOMPOSE=off` keeps a
candidate out of the reading without keeping it off the remote. Driven end to
end through the shared dev-fix publication, the shortest whole tick that ends
in a gated push.

The window past that push is in `test_published_gate_receipts.py`, and the
readings the gate refuses on are in `test_published_gate_refusals.py`.
"""
from __future__ import annotations

import unittest

from orchestrator.workflow.stages.implementing import state as _implementing_state
from tests.workflow.stages.fixing import (
    fixing_test_support as fixing,
    published_gate_support as support,
)

AT_THE_CEILING = support.AT_THE_CEILING
BASE_OBJECT_PRESENT = support.BASE_OBJECT_PRESENT
CEILING = support.CEILING
COUNT_ADDED_LINES = support.COUNT_ADDED_LINES
FREEZE_BASE_COMMIT = support.FREEZE_BASE_COMMIT
LABEL_DECOMPOSING = support.LABEL_DECOMPOSING
MEASURED_BASE_SHA = support.MEASURED_BASE_SHA
MEASURED_CANDIDATE_SHA = support.MEASURED_CANDIDATE_SHA
PAST_THE_CEILING = support.PAST_THE_CEILING
UNDER_THE_CEILING = support.UNDER_THE_CEILING
_SizeGateFixtureMixin = support._SizeGateFixtureMixin
recorded_generation = support.recorded_generation

FIXING = fixing.FIXING
ISSUE = fixing.ISSUE
PR_HEAD_SHA = fixing.PR_HEAD_SHA
PR_NUMBER = fixing.PR_NUMBER
PUSH_BRANCH = fixing.PUSH_BRANCH
SHA_BEFORE = fixing.SHA_BEFORE
STAGE_FIXING = fixing.STAGE_FIXING
VALIDATING = fixing.VALIDATING
config = fixing.config
patch = fixing.patch

_HELD = (ISSUE, LABEL_DECOMPOSING)
# The two keywords a gated push names its commit and pins its ref by.
REVISION = "revision"
LEASE = "force_with_lease"
WRITE_PINNED_STATE = "write_pinned_state"
WRITE_REJECTED = "pinned write rejected"
SET_WORKFLOW_LABEL = "set_workflow_label"
RELABEL_REJECTED = "label write rejected"
# A second pull request on the same branch, for the record frozen on the
# first: the same head can be the tip of both.
OTHER_PR_NUMBER = PR_NUMBER + 1
# A path no checkout is at, for the host the frozen pair was not made on.
ABSENT_WORKTREE = fixing.Path("/tmp/orchestrator-absent-checkout")
REVIEW_ROUND = fixing.REVIEW_ROUND
PENDING_FIX_AT = fixing.PENDING_FIX_AT

# How many readings one frozen pair may lose to the transport before the gate
# stops taking them again by itself. Read off the owner rather than spelled
# again, so a case names the bound rather than a number beside it.
_MISS_BOUND = _implementing_state._MEASUREMENT_MISSES_BEFORE_PARK

# The park a measurement nobody could take leaves, spelled as the pinned
# reason a later poll reads it back by.
PARK_MEASUREMENT_FAILED = support.PARK_MEASUREMENT_FAILED

# The two ways this host can fail to reach the base, in the order a transport
# coming back part-way produces them: a remote that names nothing at all, and
# then one that names the commit while a fetch still brings no object here.
_UNNAMED_BASE = support.FrozenCommit(
    failure=support.MeasurementFailure.BASE_UNREADABLE,
)
_UNFETCHED_BASE = support.FrozenCommit(
    sha=MEASURED_BASE_SHA, failure=support.MeasurementFailure.BASE_ABSENT,
)

# A refusal no retry can change: the checkout carries something that decides
# what counts as text, so every poll past the park stops in the same place.
_UNPINNABLE_DIFF = support.MeasurementFailure.DIFF_UNPINNABLE

# How many polls a case drives: one to take the park, and two past it, so a
# second notice would have somewhere to appear.
_POLLS_PAST_A_PARK = 3


def _after_misses(lost: int, announced=None) -> dict:
    """The record a pair that has lost `lost` readings in a row is retried from.

    `announced` is the step a notice on the thread already named, which only a
    pair whose bound has run out carries: a quiet miss tells nobody anything,
    so it leaves that field exactly as it found it.
    """
    return recorded_generation(
        measurement_miss_count=lost,
        measurement_failure=announced,
    )


class CumulativeCountTest(unittest.TestCase, _SizeGateFixtureMixin):
    """What the count is taken over once a pull request carries the work."""

    def test_the_count_covers_the_whole_pull_request(self) -> None:
        # The pair is the remote base and the candidate, so the number is what
        # the pull request COMES TO with this commit in it. Taken from the
        # head the pull request stands on -- or from the head the run started
        # at -- it would report only what this one fix changed, and a branch
        # could be grown past the ceiling one small fix at a time.
        scenario = self._seed_fix_round()

        counted = self._run_fix_round(scenario)[COUNT_ADDED_LINES]

        counted.assert_called_once()
        measured = counted.call_args.args[1:]
        self.assertEqual(measured, (MEASURED_BASE_SHA, MEASURED_CANDIDATE_SHA))
        self.assertNotIn(PR_HEAD_SHA, measured)
        self.assertNotIn(SHA_BEFORE, measured)

    def test_the_ceiling_is_passed_strictly(self) -> None:
        # A candidate exactly at the configured value joins the pull request,
        # so retuning the threshold cannot move the trigger by one line.
        for additions, published in (
            (UNDER_THE_CEILING, True),
            (AT_THE_CEILING, True),
            (PAST_THE_CEILING, False),
        ):
            with self.subTest(additions=additions):
                scenario = self._seed_fix_round()

                pushed = self._measured(scenario, additions)[PUSH_BRANCH]

                self.assertEqual(pushed.called, published)
                self.assertEqual(
                    _HELD in scenario.github.label_history, not published,
                )

    def test_the_push_carries_both_frozen_commits(self) -> None:
        # The two races either half alone leaves open. Named against the
        # commit that was measured, a checkout something moved between the
        # reading and the push publishes the measured commit rather than
        # whatever it became. Leased against the head the entry froze, a pull
        # request somebody pushed to in that same window rejects this push
        # instead of being overwritten by work measured against the head it
        # used to be on.
        scenario = self._seed_fix_round()

        pushed = self._run_fix_round(scenario)[PUSH_BRANCH].call_args

        self.assertEqual(pushed.kwargs[REVISION], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.kwargs[LEASE], PR_HEAD_SHA)

    def test_the_switch_keeps_what_the_caller_named(self) -> None:
        # No entry was frozen, so this owner read no pull request. What the
        # CALLER established is another matter and is carried through: the
        # head the fix round began at is its own claim about the ref it is
        # rewriting, and dropping it would make `DECOMPOSE=off` the setting
        # that turns a lease into a blind force-push. The COMMIT is named all
        # the same, off the checkout: the switch keeps candidates out of the
        # measurement, not out of a push that knows what it is publishing.
        scenario = self._seed_fix_round()

        with patch.object(config, support.DECOMPOSE, False):
            pushed = self._run_fix_round(scenario)[PUSH_BRANCH].call_args

        self.assertEqual(pushed.kwargs[REVISION], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.kwargs[LEASE], fixing.SHA_BEFORE)

    def test_the_switch_still_hands_the_issue_on(self) -> None:
        # The far-side proof is a claim about the commit that went out, so an
        # unnamed one reads every checkout as moved: an install running with
        # the gate off would push, record an empty receipt, and then park the
        # issue for a head sitting exactly where it was left.
        scenario = self._seed_fix_round()

        with patch.object(config, support.DECOMPOSE, False):
            self._run_fix_round(scenario)

        self.assertIn(
            (ISSUE, VALIDATING), scenario.github.label_history,
        )
        pinned = scenario.github.pinned_data(ISSUE)
        self.assertFalse(pinned[fixing.AWAITING_HUMAN])
        self.assertNotIn(fixing.PARK_REASON, pinned)
        self.assertEqual(
            pinned[support.KEY_RECEIPT_SHA], MEASURED_CANDIDATE_SHA,
        )

    def test_a_small_candidate_joins_the_pull_request(self) -> None:
        # Measured, under the ceiling, pushed onto the pull request, and the
        # issue handed back for another review pass. The generation is dropped
        # with the push and so is the debt it recorded -- an approval left
        # standing would freeze this branch out of the base refresh with
        # nothing coming back to drop it.
        scenario = self._seed_fix_round()

        pushed = self._run_fix_round(scenario)[PUSH_BRANCH]

        pushed.assert_called_once()
        self.assertIn((ISSUE, VALIDATING), scenario.github.label_history)
        pinned = scenario.github.pinned_data(ISSUE)
        self.assertNotIn(support.KEY_CANDIDATE_SHA, pinned)
        self.assertIsNone(pinned.get(support.KEY_APPROVED_SHA))

    def _measured(self, scenario, additions):
        with patch.object(config, support.MAX_ADDED_LINES, CEILING):
            return self._run_fix_round(scenario, added_lines=additions)


class OversizedCandidateTest(unittest.TestCase, _SizeGateFixtureMixin):
    """What an oversized cumulative candidate earns instead of the push."""

    def setUp(self) -> None:
        self.scenario = self._seed_fix_round()
        with patch.object(config, support.MAX_ADDED_LINES, CEILING):
            self.mocks = self._run_fix_round(
                self.scenario, added_lines=PAST_THE_CEILING,
            )

    def test_it_is_held_off_the_pull_request(self) -> None:
        self._assert_held(self.scenario, self.mocks)
        self.assertEqual(self.scenario.github.label_history, [_HELD])

    def test_the_hold_records_its_publication(self) -> None:
        # The record the coordinator is handed says which pull request the
        # candidate would have joined and the head it was standing on, beside
        # the pair and the ceiling every hold records. None of the three can
        # be re-derived once the adjudication label has replaced the one the
        # issue came from.
        pinned = self.scenario.github.pinned_data(ISSUE)

        self.assertEqual(
            pinned[support.KEY_CANDIDATE_SHA], MEASURED_CANDIDATE_SHA,
        )
        self.assertEqual(pinned[support.KEY_BASE_SHA], MEASURED_BASE_SHA)
        self.assertEqual(pinned[support.KEY_THRESHOLD], CEILING)
        self.assertEqual(pinned[support.KEY_ADDITIONS], PAST_THE_CEILING)
        self._assert_publication(pinned)

    def test_the_hold_says_nothing_was_pushed(self) -> None:
        posted = self.scenario.github.posted_comments
        notice = posted[-1][1]

        self.assertIn(f"#{PR_NUMBER}", notice)
        self.assertIn(MEASURED_CANDIDATE_SHA, notice)
        self.assertIn(PR_HEAD_SHA, notice)

    def test_the_reading_is_reported_from_its_stage(self) -> None:
        # Filed under the stage the reading was taken in rather than under the
        # package the gate lives in, so a measurement taken on a fix loop is
        # not analyzed as one an implementer's first push made.
        measurements = [
            record for record in self.scenario.github.recorded_events
            if record.get("event") == support.EVENT_LATE_MEASUREMENT
        ]

        self.assertEqual(len(measurements), 1)
        self.assertEqual(measurements[0]["stage"], STAGE_FIXING)

    def _assert_publication(self, pinned) -> None:
        self.assertEqual(pinned[support.KEY_PHASE], support.PHASE_MEASURING)
        self.assertTrue(pinned[support.KEY_POST_PUBLICATION])
        self.assertEqual(pinned[support.KEY_SOURCE_STAGE], FIXING)
        self.assertEqual(pinned[support.KEY_PUBLISHED_PR], PR_NUMBER)
        self.assertEqual(pinned[support.KEY_PUBLISHED_SHA], PR_HEAD_SHA)


class RecordedPairRetryTest(unittest.TestCase, _SizeGateFixtureMixin):
    """A pair this issue already froze is re-measured, never re-derived."""

    def test_the_recorded_pair_is_measured_again(self) -> None:
        # A tick that died between the freeze and the count comes back to the
        # pair it froze. Asking the remote for a base again would answer with
        # wherever the branch has moved to, so the same generation would be
        # settled on a different question -- the recorded object is proved
        # present instead.
        scenario = self._seed_fix_round(**recorded_generation())

        mocks = self._run_fix_round(scenario)

        mocks[FREEZE_BASE_COMMIT].assert_not_called()
        mocks[BASE_OBJECT_PRESENT].assert_called_once()
        self.assertEqual(
            mocks[COUNT_ADDED_LINES].call_args.args[1:],
            (MEASURED_BASE_SHA, MEASURED_CANDIDATE_SHA),
        )
        mocks[PUSH_BRANCH].assert_called_once()

    def test_a_recorded_count_settles_unread(self) -> None:
        # The record already answers the size question for the commit in hand,
        # so the reading is acted on rather than re-taken -- under the ceiling
        # that generation was frozen at, so a threshold retuned between two
        # ticks cannot re-judge a candidate mid-flight.
        scenario = self._seed_fix_round(
            **recorded_generation(additions=PAST_THE_CEILING),
        )

        mocks = self._run_fix_round(scenario)

        self._assert_unmeasured(mocks)
        self._assert_held(scenario, mocks)
        self.assertEqual(scenario.github.label_history, [_HELD])

    def test_a_base_the_fetch_lost_is_counted(self) -> None:
        # The object the recorded count is taken against is not here and a
        # fetch did not bring it back: the transport rather than the pull
        # request, so the reading is counted and nothing is said. The pair
        # stays exactly as it is, the remote is not asked for a different
        # base, and nothing is pushed onto a pull request nobody measured.
        scenario = self._seed_fix_round(**recorded_generation())

        mocks = self._run_fix_round(scenario, base_object_present=False)

        mocks[FREEZE_BASE_COMMIT].assert_not_called()
        self._assert_unmeasured(mocks)
        self._assert_held(scenario, mocks)
        self._assert_missed(scenario)
        pinned = self._pinned(scenario)
        self.assertEqual(pinned[support.KEY_BASE_SHA], MEASURED_BASE_SHA)
        self.assertEqual(
            pinned[support.KEY_CANDIDATE_SHA], MEASURED_CANDIDATE_SHA,
        )

    def test_the_bound_hands_the_pair_over_once(self) -> None:
        # Driven as the consecutive polls it really is, because the mention is
        # what a seeded count cannot check: this reading is re-entered ahead
        # of the handler on EVERY poll, so a bound counted afresh each time --
        # or a park cleared on the way into the gate -- reads exactly like a
        # working retry while it asks a human once a poll and never stops
        # counting. Three readings the pair may lose in a row, a fourth that
        # hands it over, and past that a tick that holds silently: the park it
        # already took is still true, and the stage below still may not run
        # over an unmeasured candidate.
        scenario = self._seed_fix_round(**recorded_generation())

        for poll in range(1, _MISS_BOUND + 3):
            with self.subTest(poll=poll):
                handled, _mocks = self._poll(
                    scenario, base_object_present=False,
                )

                self.assertFalse(handled)
                if poll <= _MISS_BOUND:
                    self._assert_missed(scenario, count=poll)
                    continue
                self._assert_parked(scenario)
                self.assertEqual(len(scenario.github.posted_comments), 1)
                self.assertIn(
                    config.HITL_MENTIONS, scenario.github.posted_comments[0][1],
                )
                self.assertEqual(
                    self._pinned(scenario)[support.KEY_MISS_COUNT],
                    _MISS_BOUND + 1,
                )

    def test_a_reading_that_lands_unparks_the_pair(self) -> None:
        # The other half of the park above, and the only thing that ends it
        # here: no human answers a reading on this road, so what retires the
        # park is the reading itself, taken on an ordinary poll once the
        # transport is back. The row of lost readings ends with it.
        scenario = self._seed_fix_round(**_after_misses(_MISS_BOUND))
        self._poll(scenario, base_object_present=False)

        with patch.object(config, support.MAX_ADDED_LINES, CEILING):
            mocks = self._poll(scenario, added_lines=PAST_THE_CEILING)[1]

        mocks[COUNT_ADDED_LINES].assert_called_once()
        pinned = self._pinned(scenario)
        self.assertFalse(pinned[fixing.AWAITING_HUMAN])
        self.assertIsNone(pinned[fixing.PARK_REASON])
        self.assertNotIn(support.KEY_MISS_COUNT, pinned)
        # And the step that park's notice named goes with it. The record this
        # write leaves is the one the adjudication is driven from, so a member
        # carried into it would describe a refusal that is over on an issue
        # where nothing is refusing anything.
        self.assertNotIn(support.KEY_MEASUREMENT_FAILURE, pinned)

    def test_the_count_is_durable_before_the_mention(self) -> None:
        # Every tick is a fresh process, so a miss a human is told about
        # before it is written down is one a crash in that window loses --
        # and the next reading would start the bound over. Read off what the
        # pinned comment carried when the notice went out.
        scenario = self._seed_fix_round(**_after_misses(_MISS_BOUND))
        mentioned = support._RecordAtNotice(scenario.github)

        with mentioned.held():
            self._run_fix_round(scenario, base_object_present=False)

        self.assertEqual(
            mentioned.pinned[support.KEY_MISS_COUNT],
            _MISS_BOUND + 1,
        )
        # The step that mention names rides the same write, because the guard
        # that keeps the polls after it silent is the one that reads it back.
        self.assertEqual(
            mentioned.pinned[support.KEY_MEASUREMENT_FAILURE],
            support.MeasurementFailure.BASE_ABSENT,
        )

    def _assert_missed(self, scenario, count: int = 1) -> None:
        """One reading the transport lost, counted and otherwise unsaid.

        The count is the whole of what a miss inside the bound leaves: the
        step it stopped at is said to the log and to both streams and to no
        human, so nothing on the issue says one is waiting and the next poll
        re-enters the same pair by itself.
        """
        pinned = self._pinned(scenario)
        self.assertEqual(pinned[support.KEY_MISS_COUNT], count)
        self.assertNotIn(support.KEY_MEASUREMENT_FAILURE, pinned)
        self.assertFalse(pinned.get(fixing.AWAITING_HUMAN))
        self.assertIsNone(pinned.get(fixing.PARK_REASON))
        self.assertEqual(scenario.github.posted_comments, [])


class StandingParkTest(unittest.TestCase, _SizeGateFixtureMixin):
    """What a park that is still standing owes each reading past it.

    The reading is re-entered on every poll by design -- that is how a
    transport coming back settles a pair with no human at all -- so what those
    polls owe the thread is one sentence per thing there is to say rather than
    one per poll.
    """

    def test_a_repeated_cause_is_said_once(self) -> None:
        # A diff nothing here can pin is the sharpest case: it does not clear
        # itself, so the polls go on for as long as the checkout carries
        # whatever was planted in it, and a notice on each of them would
        # mention the same people once a poll until they cleared it.
        scenario = self._seed_fix_round(**recorded_generation())

        for _ in range(_POLLS_PAST_A_PARK):
            self._poll(scenario, added_lines=_UNPINNABLE_DIFF)

        self.assertEqual(len(scenario.github.posted_comments), 1)
        self.assertIn(
            _UNPINNABLE_DIFF, scenario.github.posted_comments[0][1],
        )
        self.assertEqual(
            self._pinned(scenario)[support.KEY_MEASUREMENT_FAILURE],
            _UNPINNABLE_DIFF,
        )

    def test_an_unnamed_step_is_announced_once(self) -> None:
        # The park spares the thread a repeat, not a new fact. A remote that
        # has come back far enough to NAME the base while a fetch still brings
        # nothing back is a different sentence and a different next move from
        # the one this human was sent, so it is said -- once, with the record
        # moved to it in the write the notice rides out on, and never again
        # for as long as the reading stops there.
        scenario = self._seed_fix_round(**{
            fixing.AWAITING_HUMAN: True,
            fixing.PARK_REASON: PARK_MEASUREMENT_FAILED,
            **recorded_generation(
                base_sha="",
                measurement_miss_count=_MISS_BOUND + 1,
                measurement_failure=support.MeasurementFailure.BASE_UNREADABLE,
            ),
        })
        announced = support._RecordAtNotice(scenario.github)

        self._poll(scenario, frozen_base=_UNNAMED_BASE)
        self.assertEqual(scenario.github.posted_comments, [])
        with announced.held():
            self._poll(scenario, frozen_base=_UNFETCHED_BASE)
        self._poll(scenario, base_object_present=False)

        self.assertEqual(len(scenario.github.posted_comments), 1)
        self.assertIn(
            support.MeasurementFailure.BASE_ABSENT,
            scenario.github.posted_comments[0][1],
        )
        self.assertEqual(
            announced.pinned[support.KEY_MEASUREMENT_FAILURE],
            support.MeasurementFailure.BASE_ABSENT,
        )
        pinned = self._pinned(scenario)
        self.assertEqual(pinned[support.KEY_MISS_COUNT], _MISS_BOUND + 1)
        self.assertEqual(pinned[fixing.PARK_REASON], PARK_MEASUREMENT_FAILED)


class SwitchedOffTest(unittest.TestCase, _SizeGateFixtureMixin):
    """`DECOMPOSE=off` keeps a fix out of the gate and out of its costs."""

    def test_the_switch_publishes_without_reading(self) -> None:
        scenario = self._seed_fix_round()

        with patch.object(config, support.DECOMPOSE, False):
            mocks = self._run_fix_round(scenario)

        mocks[COUNT_ADDED_LINES].assert_not_called()
        mocks[PUSH_BRANCH].assert_called_once()
        self.assertNotIn(
            support.KEY_CANDIDATE_SHA, scenario.github.pinned_data(ISSUE),
        )

    def test_a_fresh_candidate_supersedes_a_record(self) -> None:
        # The record names a commit an earlier tick froze and the checkout has
        # moved past it: the developer was resumed on a human's guidance and
        # committed again. That is new work, which the switch keeps out of the
        # reading -- so the record it supersedes is retired and the commit
        # goes out named against the checkout and pinned to the frozen head.
        # A verdict naming no commit here would be read as an approval for the
        # empty SHA and park the round for a lease no approval ever wrote.
        scenario = self._seed_fix_round(**recorded_generation(
            candidate_sha=support.SUPERSEDED_CANDIDATE,
        ))

        with patch.object(config, support.DECOMPOSE, False):
            mocks = self._run_fix_round(scenario)

        mocks[COUNT_ADDED_LINES].assert_not_called()
        pushed = mocks[PUSH_BRANCH].call_args
        self.assertEqual(pushed.kwargs[REVISION], MEASURED_CANDIDATE_SHA)
        self.assertEqual(pushed.kwargs[LEASE], PR_HEAD_SHA)

    def test_a_superseded_record_is_retired(self) -> None:
        # Left standing, a `late_candidate_sha` naming work no longer on the
        # branch freezes this branch out of the pre-tick base refresh for good
        # and reads as a live cycle to the guard that ends one on a close.
        scenario = self._seed_fix_round(**recorded_generation(
            candidate_sha=support.SUPERSEDED_CANDIDATE,
        ))

        with patch.object(config, support.DECOMPOSE, False):
            self._run_fix_round(scenario)

        pinned = scenario.github.pinned_data(ISSUE)
        self.assertNotIn(support.KEY_CANDIDATE_SHA, pinned)
        self.assertIn((ISSUE, VALIDATING), scenario.github.label_history)
