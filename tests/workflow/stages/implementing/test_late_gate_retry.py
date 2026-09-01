# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a human's reply to a measurement park buys, and what it may not.

A bare `/orchestrator continue` buys a second reading of the EXACT pair that
was recorded and nothing else -- no agent, and no substitute for a commit the
record names. Guidance buys the opposite: the developer is resumed, and what
it leaves is judged against the floor the park left on the branch rather than
against the base, so a clarifying question is not answered by publishing the
work it was asked about.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.git.measurement.models import FrozenCommit, MeasurementFailure

from tests.workflow.fixtures import (
    LABEL_DECOMPOSING,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
    _agent,
)
from tests.workflow.stages.implementing import late_gate_test_support as support

_MOVED_SHA = "e" * SHA_LENGTH
# What a checkout somebody moved reads as, and the two successive readings of
# one that moves mid-tick: the recorded commit when a reconciliation proves it
# before starting, and something else by the time the gate reads it again.
# Nothing of this tick's put it there.
_MOVED_HEAD = FrozenCommit(sha=_MOVED_SHA)
_HEAD_MOVES = (FrozenCommit(sha=MEASURED_CANDIDATE_SHA), _MOVED_HEAD)
# The same move onto a commit this host names and cannot peel: an object a
# prune took, or work made somewhere else. It carries an id, which is what
# makes it the sharpest of these -- a name is exactly what a park records.
_HEAD_MOVES_TO_ABSENT = (
    FrozenCommit(sha=MEASURED_CANDIDATE_SHA),
    FrozenCommit(
        sha=_MOVED_SHA, failure=MeasurementFailure.CANDIDATE_ABSENT,
    ),
)

# What a checkout a recordless park comes back to can be standing on, none of
# which anything ties to this issue: the commit the developer left, one a
# rebase or reset moved it to, and one a rebuilt worktree cannot name at all.
_RECORDLESS_CHECKOUTS = (
    ("the head it was left on", None),
    ("a head somebody moved", _MOVED_HEAD),
    ("a head nothing can read", FrozenCommit(
        failure=MeasurementFailure.CANDIDATE_UNREADABLE,
    )),
)

# Each of them under both switch settings, since the switch decides what
# ENTERS the gate and decides nothing about a park already waiting on one.
_RECORDLESS_RETRIES = tuple(
    (checkout, head, decomposing)
    for checkout, head in _RECORDLESS_CHECKOUTS
    for decomposing in (True, False)
)
_REAPED_WORKTREE = support.Path("/nonexistent/orchestrator-reaped-worktree")
_DECOMPOSING = (support.GATE_ISSUE_NUMBER, LABEL_DECOMPOSING)
_AGENT_TIMEOUT = "agent_timeout"
_PRE_IMPLEMENT_SHA = "pre_implement_sha"
_PRE_TIMEOUT_SHA = "sha-pre"
_POST_TIMEOUT_SHA = "sha-post"
# The sentence the generic parked-continue classifier posts, which a
# measurement park must never reach.
_NEEDS_GUIDANCE = "needs your actual guidance"
_DECOMPOSE = "DECOMPOSE"
# The reply a human writes to make the developer change the work, and
# what a resumed run says when it has.
_GUIDANCE = "drop the generated fixtures from this"
_FINISHED = "done"
# What a resumed run says when it answered instead of building.
_ASKED = "which half of this did you mean?"


class LateGateTimeoutRecoveryTest(support._GateCase, unittest.TestCase):
    """A commit recovered from a timeout is the same kind of candidate."""

    def test_a_recovered_commit_is_measured(self) -> None:
        # The recovery publishes without a human and without an agent, which
        # is exactly why it may not publish around the gate: an oversized
        # candidate would reach a branch and a pull request on the strength of
        # a run nobody read.
        self._seed(**{
            support.AWAITING_HUMAN: True,
            support.PARK_REASON: _AGENT_TIMEOUT,
            _PRE_IMPLEMENT_SHA: _PRE_TIMEOUT_SHA,
        })

        mocks = self._run_gate(
                head_shas=(_POST_TIMEOUT_SHA,),
                added_lines=support.OVERSIZED_ADDITIONS,
            )

        self._assert_no_agent(mocks)
        self._assert_measured(mocks)
        self._assert_held(mocks)
        self.assertIn(_DECOMPOSING, self.github.label_history)


class LateGateStrandedPairTest(support._GateCase, unittest.TestCase):
    """A frozen pair with no park beside it, on a host that cannot show it.

    The crash window the persist-before-count ordering opens: the pair went
    down durably and the tick died before it was counted or parked, so nothing
    on the issue says the workflow is waiting for anything. On the host that
    froze it the next tick simply measures again; on a rebuilt one the
    checkout comes back at base and the ordinary flow would pay for a second
    developer over work the first one already finished.
    """

    def setUp(self) -> None:
        super().setUp()
        self._seed(**support.recorded_generation())

    def test_a_reaped_worktree_parks_before_spawning(self) -> None:
        mocks = self._run_gate(
            worktree=_REAPED_WORKTREE, has_new_commits=False,
        )

        self._assert_no_agent(mocks)
        self._assert_unmeasured(mocks)
        self._assert_held(mocks)
        self._assert_parked()

    def test_an_absent_object_parks_before_spawning(self) -> None:
        # The checkout is there and the commit is not: a rebuilt host, or one
        # the branch never reached. A fresh run would produce different work,
        # so what the park asks for is the worktree rather than another agent.
        mocks = self._run_gate(
            recorded_commit=FrozenCommit(
                failure=MeasurementFailure.CANDIDATE_ABSENT,
            ),
            has_new_commits=False,
        )

        self._assert_no_agent(mocks)
        self._assert_held(mocks)
        self._assert_parked()

    def test_the_record_survives_for_the_retry(self) -> None:
        self._run_gate(worktree=_REAPED_WORKTREE, has_new_commits=False)

        self._assert_frozen()

    def test_a_base_free_branch_still_reconciles(self) -> None:
        # The reading that would otherwise send this issue to a second
        # developer: "is there work to publish" is answered downstream by
        # asking whether the branch is ahead of the CURRENT base, and a base
        # that has since absorbed the candidate -- or a probe that could not
        # answer -- reads as a branch carrying nothing. The record names the
        # pair outright, so no heuristic is consulted at all.
        mocks = self._run_gate(
            has_new_commits=False, added_lines=support.SMALL_ADDITIONS,
        )

        self._assert_no_agent(mocks)
        self._assert_measured(mocks)
        self._assert_published(mocks)

    def test_a_missing_recorded_base_parks(self) -> None:
        # The other end of the pair, proved for the same reason: a host that
        # cannot show the object the count is taken against can neither
        # measure it nor defend a verdict over it.
        mocks = self._run_gate(
            has_new_commits=False, base_object_present=False,
        )

        self._assert_no_agent(mocks)
        self._assert_unmeasured(mocks)
        self._assert_held(mocks)
        self._assert_parked()


class LateGateMovedPairTest(support._GateCase, unittest.TestCase):
    """A frozen pair whose checkout is no longer on the recorded commit.

    No developer ran on this path, so a head somewhere else is not fresh
    output: it is a checkout somebody moved, and measuring it would answer the
    size question about a commit nobody froze.
    """

    def setUp(self) -> None:
        super().setUp()
        self._seed(**support.recorded_generation())

    def test_a_moved_checkout_parks(self) -> None:
        # No developer ran on this path -- the run whose work this is finished
        # before the crash -- so a head somewhere else is not fresh output to
        # be measured in the recorded candidate's place. It is a checkout
        # somebody moved, and measuring it would answer the size question
        # about a commit nobody froze while the record naming the real one was
        # discarded.
        mocks = self._run_gate(
            has_new_commits=False,
            candidate_commit=_MOVED_HEAD,
        )

        self._assert_no_agent(mocks)
        self._assert_unmeasured(mocks)
        self._assert_held(mocks)
        self._assert_parked()
        self._assert_frozen()

    def test_a_moved_checkout_parks_switched_off(self) -> None:
        # The switch decides whether NEW work is measured. Nothing here is
        # new: it is a reading a crashed tick recorded, and publishing the
        # head in its place is the switch failing open.
        with patch.object(config, _DECOMPOSE, False):
            mocks = self._run_gate(
                has_new_commits=False,
                candidate_commit=_MOVED_HEAD,
            )

        self._assert_no_agent(mocks)
        self._assert_held(mocks)
        self._assert_parked()
        self._assert_frozen()

    def test_a_head_that_moves_mid_tick_parks(self) -> None:
        # The head is proved against the record before this reconciliation
        # starts and read again inside the gate a moment later, and the
        # checkout is writable in between. No run of this tick produced
        # whatever it moved to -- so reading it as fresh work would measure
        # and publish it with the switch on, and push it unmeasured with the
        # switch off, both about a commit this reconciliation was never about.
        for decomposing in (True, False):
            with self.subTest(decompose=decomposing):
                self.setUp()

                with patch.object(config, _DECOMPOSE, decomposing):
                    mocks = self._run_gate(
                        has_new_commits=False, candidate_commit=_HEAD_MOVES,
                    )

                self._assert_no_agent(mocks)
                self._assert_unmeasured(mocks)
                self._assert_held(mocks)
                self._assert_parked()
                self._assert_frozen()

    def test_a_move_onto_an_absent_object_parks(self) -> None:
        # The same race with a head that NAMES a commit this host cannot peel.
        # A named one handed back from the reconciliation is one the park
        # downstream records -- minting a generation around it and dropping
        # the pair this retry exists to re-read -- so the refusal has to come
        # before the readability question rather than after it.
        for decomposing in (True, False):
            with self.subTest(decompose=decomposing):
                self.setUp()

                with patch.object(config, _DECOMPOSE, decomposing):
                    mocks = self._run_gate(
                        has_new_commits=False,
                        candidate_commit=_HEAD_MOVES_TO_ABSENT,
                    )

                self._assert_no_agent(mocks)
                self._assert_unmeasured(mocks)
                self._assert_held(mocks)
                self._assert_parked()
                self._assert_frozen()

    def test_the_switch_off_still_reconciles_the_pair(self) -> None:
        # And where the checkout IS on the recorded commit, the reading the
        # crashed tick recorded is taken with the switch either way: the
        # candidate was in the gate before the switch was touched.
        with patch.object(config, _DECOMPOSE, False):
            mocks = self._run_gate(
                has_new_commits=False, added_lines=support.SMALL_ADDITIONS,
            )

        self._assert_no_agent(mocks)
        self._assert_measured(mocks)
        self._assert_published(mocks)

    def test_the_host_that_froze_it_measures_again(self) -> None:
        # The ordinary recovery, and the reason the probe is a proof rather
        # than a refusal: where the commits really are there, the tick picks
        # them up and the gate reads the same pair a second time.
        mocks = self._run_gate(added_lines=support.SMALL_ADDITIONS)

        self._assert_no_agent(mocks)
        self._assert_measured(mocks)
        self._assert_published(mocks)


class LateGateContinueTest(support._ParkedRetryCase, unittest.TestCase):
    """The bare continue a measurement park earns, and what it may not buy."""

    def test_a_bare_continue_remeasures(self) -> None:
        # What failed was a reading, and the developer that produced the commit
        # finished long ago: another run would buy a second answer to a
        # question nobody asked.
        self._park(support.BARE_CONTINUE)

        mocks = self._run_gate(added_lines=support.SMALL_ADDITIONS)

        self._assert_no_agent(mocks)
        self._assert_measured(mocks)
        self._assert_published(mocks)
        pinned = self._pinned()
        self.assertFalse(pinned.get(support.AWAITING_HUMAN))
        self.assertEqual(
            pinned[support.LAST_ACTION_COMMENT_ID], support.REPLY_COMMENT_ID,
        )

    def test_a_failed_retry_parks_again(self) -> None:
        self._park(support.BARE_CONTINUE)

        mocks = self._run_gate(added_lines=MeasurementFailure.DIFF_FAILED)

        self._assert_no_agent(mocks)
        self._assert_held(mocks)
        self._assert_parked()


    def test_a_moved_head_refuses_the_bare_retry(self) -> None:
        # No agent ran, so a head somewhere else is not work this workflow
        # produced: the retry reads the exact pair that was recorded, and
        # measuring anything else answers the size question about a commit
        # nobody froze.
        self._park(support.BARE_CONTINUE)

        mocks = self._run_gate(
            candidate_commit=_MOVED_HEAD,
        )

        self._assert_no_agent(mocks)
        self._assert_unmeasured(mocks)
        self._assert_held(mocks)
        self._assert_parked()
        self._assert_frozen()

    def test_a_head_that_moves_mid_retry_parks(self) -> None:
        # The same race one road over: the bare continue proves the head
        # against the record, and the gate reads it again. What the retry
        # buys is a second reading of the EXACT pair, so the pair outlives a
        # head that moved under it rather than being superseded by one.
        for decomposing in (True, False):
            with self.subTest(decompose=decomposing):
                self.setUp()
                self._park(support.BARE_CONTINUE)

                with patch.object(config, _DECOMPOSE, decomposing):
                    mocks = self._run_gate(candidate_commit=_HEAD_MOVES)

                self._assert_no_agent(mocks)
                self._assert_unmeasured(mocks)
                self._assert_held(mocks)
                self._assert_parked()
                self._assert_frozen()

    def test_the_switch_off_refuses_it_too(self) -> None:
        # Publishing it unmeasured is the one thing the switch may not buy: no
        # reading covers that branch, and the record still names another one.
        self._park(support.BARE_CONTINUE)

        with patch.object(config, "DECOMPOSE", False):
            mocks = self._run_gate(
                candidate_commit=_MOVED_HEAD,
            )

        self._assert_no_agent(mocks)
        self._assert_held(mocks)
        self._assert_parked()
        self._assert_frozen()


class LateGateGuidanceTest(support._ParkedRetryCase, unittest.TestCase):
    """Guidance resumes the developer, and the floor judges what it left."""

    def test_guidance_reaches_the_developer(self) -> None:
        # A reply with words in it is not a retry of the reading: the human is
        # asking for the work itself to change, which is the ordinary resume.
        self._park(_GUIDANCE)

        mocks = self._run_gate(
            run_agent=_agent(session_id=support.DEV_SESSION, last_message=_FINISHED),
            head_shas=(MEASURED_CANDIDATE_SHA, _MOVED_SHA),
            added_lines=support.SMALL_ADDITIONS,
        )

        self._assert_resumed(mocks)

    def test_a_resumed_question_publishes_nothing(self) -> None:
        # The park left committed work on the branch, so "ahead of base" says
        # nothing about what THIS run did. A developer that answered with a
        # question and committed nothing leaves HEAD on the recorded
        # candidate -- and publishing that would push the very commit whose
        # size nobody could read, over the question it was asked instead.
        self._park("which half of this is generated?")

        mocks = self._run_gate(
            run_agent=_agent(
                session_id=support.DEV_SESSION, last_message="Which fixtures do you mean?",
            ),
            head_shas=(MEASURED_CANDIDATE_SHA, MEASURED_CANDIDATE_SHA),
            added_lines=support.SMALL_ADDITIONS,
        )

        self._assert_resumed(mocks)
        self._assert_unmeasured(mocks)
        self._assert_held(mocks)
        pinned = self._pinned()
        self.assertTrue(pinned[support.AWAITING_HUMAN])
        self.assertIn(
            "Which fixtures do you mean?", self.github.posted_comments[-1][1],
        )

    def test_a_resumed_commit_advances_the_generation(self) -> None:
        # Both commits are here and a developer really did run, so the branch
        # genuinely moved: a fresh candidate under a fresh generation of the
        # same cycle, exactly as a revision under the adjudication label is.
        self._park(_GUIDANCE)

        mocks = self._run_gate(
            run_agent=_agent(
                session_id=support.DEV_SESSION, last_message=_FINISHED,
            ),
            head_shas=(MEASURED_CANDIDATE_SHA, _MOVED_SHA),
            candidate_commit=_MOVED_HEAD,
            added_lines=support.OVERSIZED_ADDITIONS,
        )

        self._assert_measured(mocks)
        self._assert_held(mocks)
        pinned = self._pinned()
        self.assertEqual(pinned[support.KEY_CANDIDATE_SHA], _MOVED_SHA)
        self.assertEqual(pinned[support.KEY_CYCLE_ID], 1)
        self.assertEqual(pinned[support.KEY_GENERATION], 2)

    def test_the_switch_off_supersedes_the_record(self) -> None:
        # Publishing the new head is what the switch says. Leaving the record
        # over work nobody is publishing is not: it names a commit this branch
        # has moved past and freezes the branch out of the base refresh.
        self._park(_GUIDANCE)
        recorded = support._RecordAtHandoff(self.github)

        with patch.object(config, _DECOMPOSE, False), recorded.held():
            mocks = self._resumed_past_the_record()

        self._assert_unmeasured(mocks)
        self._assert_published(mocks)
        pinned = self._pinned()
        self.assertNotIn(support.KEY_CANDIDATE_SHA, pinned)
        self.assertEqual(pinned[support.KEY_RETIRED_CYCLE], 1)

    def test_the_switch_off_retires_first(self) -> None:
        # And durably: what follows the retirement is a push, a pull request,
        # and the label that hands the issue to review, with the tick's own
        # write after all of it. A crash in that window would leave a
        # published pull request over a record that still says `measuring`.
        self._park(_GUIDANCE)
        recorded = support._RecordAtHandoff(self.github)

        with patch.object(config, _DECOMPOSE, False), recorded.held():
            self._resumed_past_the_record()

        self.assertNotIn(support.KEY_CANDIDATE_SHA, recorded.pinned)
        self.assertEqual(recorded.pinned[support.KEY_RETIRED_CYCLE], 1)

    def test_a_resumed_commit_is_measured(self) -> None:
        # And a run that really did commit is a fresh candidate: HEAD moved
        # off the floor the park left, so the gate measures what it produced.
        self._park(_GUIDANCE)

        mocks = self._run_gate(
            run_agent=_agent(session_id=support.DEV_SESSION, last_message=_FINISHED),
            head_shas=(MEASURED_CANDIDATE_SHA, _MOVED_SHA),
            candidate_commit=_MOVED_HEAD,
            added_lines=support.SMALL_ADDITIONS,
        )

        self._assert_resumed(mocks)
        self._assert_measured(mocks)
        self._assert_published(mocks)

    def _resumed_past_the_record(self):
        """One guidance resume whose developer committed a different SHA."""
        return self._run_gate(
            run_agent=_agent(
                session_id=support.DEV_SESSION, last_message=_FINISHED,
            ),
            head_shas=(MEASURED_CANDIDATE_SHA, _MOVED_SHA),
            candidate_commit=_MOVED_HEAD,
        )


class LateGateRecordlessRetryTest(support._ParkedRetryCase, unittest.TestCase):
    """A park a refusal took before any pair could be frozen."""

    def test_no_checkout_is_substituted_for_the_pair(self) -> None:
        # The park whose generation was never persisted: the revision would
        # not resolve, so no commit was named and the record carries none.
        # What a bare continue buys is a re-reading of the EXACT pair that was
        # recorded, and there is no pair -- so what a retry would take is a
        # FIRST reading, of whatever the checkout points at by then. Nothing
        # ties that head to this issue: a rebase, a reset, or a rebuilt
        # worktree all leave one, and measuring it publishes the base, or
        # somebody else's work, as this implementation.
        for checkout, head, decomposing in _RECORDLESS_RETRIES:
            with self.subTest(checkout=checkout, decompose=decomposing):
                self.setUp()
                self._park_without_a_record()

                with patch.object(config, _DECOMPOSE, decomposing):
                    mocks = self._run_gate(
                        added_lines=support.SMALL_ADDITIONS,
                        candidate_commit=head,
                    )

                self._assert_no_agent(mocks)
                self._assert_unmeasured(mocks)
                self._assert_held(mocks)
                self._assert_parked()

    def test_the_refusal_names_no_commit(self) -> None:
        # And what it says is true of the state it is about: nothing was
        # frozen, so the sentence may not promise a retry of a pair or name
        # the commit it would read.
        self._park_without_a_record()

        self._run_gate(candidate_commit=_MOVED_HEAD)

        notice = self.github.posted_comments[-1][1]
        self.assertIn("no commit was ever frozen", notice)
        self.assertNotIn(_MOVED_SHA, notice)
        self.assertNotIn(support.BARE_CONTINUE, notice)

    def test_a_reaped_checkout_is_still_reported(self) -> None:
        # Failure, then reap, then a bare continue: the refusal happened
        # before anything could be frozen, so the record carries no commit at
        # all -- and a report built from an empty identity is one the sinks
        # refuse, leaving the operator a park and nothing joinable to it. The
        # identity is minted for the report instead.
        self._park_without_a_record()

        self._run_gate(worktree=_REAPED_WORKTREE)

        failures = self._records(support.EVENT_LATE_FAILURE)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["failure"], "measurement_failed")
        self.assertEqual(failures[0]["cycle_id"], 1)

    def test_a_reaped_checkout_claims_no_commit(self) -> None:
        # And what it says is true of the state it is about: no commit was
        # ever recorded, so the sentence may not name one.
        self._park_without_a_record()

        self._run_gate(worktree=_REAPED_WORKTREE)

        notice = self.github.posted_comments[-1][1]
        self.assertIn("no commit was ever frozen", notice)
        self.assertNotIn(MEASURED_CANDIDATE_SHA, notice)

    def test_a_new_candidate_is_still_bypassed(self) -> None:
        # The switch is not disarmed by the flag: an issue with no park behind
        # it is ordinary new work and publishes unmeasured, as it always has.
        with patch.object(config, _DECOMPOSE, False):
            mocks = self._run_gate()

        self._assert_unmeasured(mocks)
        self._assert_published(mocks)


class LateGateRecordlessGuidanceTest(
    support._ParkedRetryCase, unittest.TestCase,
):
    """What guidance to a park that froze nothing buys, and what it may not.

    The refusal a bare continue earns is not a dead end: a reply with words in
    it is guidance, so it never reaches that refusal at all and the developer
    is resumed. What it leaves is then judged the ordinary way -- which on
    this park is the whole difficulty, because there is no record of any kind
    on the issue and the branch already carries commits nothing names.
    """

    def setUp(self) -> None:
        super().setUp()
        self._park_without_a_record(reply=_GUIDANCE)

    def test_guidance_still_reaches_the_developer(self) -> None:
        mocks = self._resumed(head_shas=(MEASURED_CANDIDATE_SHA, _MOVED_SHA))

        self._assert_resumed(mocks)
        self._assert_measured(mocks)
        self._assert_published(mocks)

    def test_a_question_parks_over_the_inherited_work(self) -> None:
        # The commits on the branch predate this run and nothing on the issue
        # names them: the refusal that took this park could not freeze a
        # candidate, so there is no floor to judge the resume against and
        # ahead-of-base says "this run committed" for a run that committed
        # nothing. Published on that reading, the developer's question is
        # dropped and work a human was still deciding about goes to review.
        mocks = self._resumed(
            head_shas=(MEASURED_CANDIDATE_SHA, MEASURED_CANDIDATE_SHA),
            last_message=_ASKED,
        )

        self._assert_resumed(mocks)
        self._assert_unmeasured(mocks)
        self._assert_held(mocks)
        self.assertIn(_ASKED, self.github.posted_comments[-1][1])
        self.assertTrue(self._pinned()[support.AWAITING_HUMAN])

    def _resumed(self, last_message: str = _FINISHED, **run_options):
        """One guidance resume, and what the checkout says it left."""
        return self._run_gate(
            run_agent=_agent(
                session_id=support.DEV_SESSION, last_message=last_message,
            ),
            added_lines=support.SMALL_ADDITIONS,
            **run_options,
        )


class LateGateReapedWorktreeTest(support._ParkedRetryCase, unittest.TestCase):
    """A checkout that is gone is answered here, not by the generic refusal."""

    def test_an_absent_worktree_parks_on_the_evidence(self) -> None:
        # The command was the right one and it is answered here, not handed to
        # the generic classifier -- which would refuse it as carrying no
        # guidance, telling the operator to answer a question nobody asked and
        # consuming their reply against it. What it may not do is re-run the
        # developer: the recorded commit is the evidence, and a fresh checkout
        # is not it.
        self._park(support.BARE_CONTINUE)

        mocks = self._run_gate(worktree=_REAPED_WORKTREE)

        self._assert_no_agent(mocks)
        self._assert_unmeasured(mocks)
        self._assert_held(mocks)
        self._assert_parked()
        posted = [body for _, body in self.github.posted_comments]
        self.assertIn("not on this host", posted[-1])
        self.assertFalse(any(_NEEDS_GUIDANCE in body for body in posted))

    def test_an_absent_worktree_keeps_the_record(self) -> None:
        # And the retry it promises has something to come back to: the pair is
        # left exactly as it was, and the failure is reported like any other.
        self._park(support.BARE_CONTINUE)

        self._run_gate(worktree=_REAPED_WORKTREE)

        self._assert_frozen()
        failures = self._records(support.EVENT_LATE_FAILURE)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["failure"], "measurement_failed")


if __name__ == "__main__":
    unittest.main()
