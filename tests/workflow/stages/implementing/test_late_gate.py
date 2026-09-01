# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The size gate between a committed candidate and the branch it publishes on.

Every clean committed candidate goes through one seam, so what these pin down
is what that seam decides once it has a number: a candidate at or below the
ceiling publishes and goes to review, one past it is held unpublished under the
adjudication label, and two are never measured at all -- the commit an
adjudication accepted, and every candidate while the switch is off. What a
reading nobody could take costs, and the evidence rules a retry re-reads it
under, are in the recovery module beside this one.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator import config
from orchestrator.git.measurement.models import FrozenCommit
from tests.workflow.fixtures import (
    LABEL_DECOMPOSING,
    LABEL_VALIDATING,
    MEASURED_BASE_SHA,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
    _agent,
    _analytics_records,
)
from tests.workflow.stages.implementing import late_gate_test_support as support

_OTHER_SHA = "d" * SHA_LENGTH
_DECOMPOSING = (support.GATE_ISSUE_NUMBER, LABEL_DECOMPOSING)
_STAGE_IMPLEMENTING = "implementing"
_DECOMPOSE = "DECOMPOSE"
_CANDIDATE_MOVED = "late_candidate_moved"
_POST_PUBLICATION = "late_post_publication"
_SOURCE_STAGE = "late_source_stage"
_PUBLISHED_PR = "late_published_pr_number"
_PUBLISHED_SHA = "late_published_sha"

# A checkout that answers the gate with the measured commit and the
# publication with a descendant: the race the handoff refuses.
_MOVING_HEAD = (
    FrozenCommit(sha=MEASURED_CANDIDATE_SHA),
    FrozenCommit(sha=_OTHER_SHA),
)

class LateGateVerdictTest(support._GateCase, unittest.TestCase):
    """What a measured candidate earns: the ordinary push, or adjudication."""

    def test_a_small_candidate_publishes(self) -> None:
        # The ordinary world: measured, under the ceiling, and published: the
        # branch is pushed, a pull request opened, and the issue handed to
        # review. The generation is dropped with it --
        # a frozen candidate freezes this branch out of the base refresh, and a
        # record carried into the stages that close the issue reads as a live
        # cycle a close should end. What outlives it is the cycle it was, so
        # the next candidate on this issue cannot answer to the same number.
        mocks = self._run_gate(added_lines=support.SMALL_ADDITIONS)

        self._assert_published(mocks)
        self.assertEqual(len(self.github.opened_prs), 1)
        self.assertIn(
            (support.GATE_ISSUE_NUMBER, LABEL_VALIDATING),
            self.github.label_history,
        )
        pinned = self._pinned()
        self.assertNotIn(support.KEY_CANDIDATE_SHA, pinned)
        self.assertEqual(pinned[support.KEY_RETIRED_CYCLE], 1)

    def test_an_oversized_candidate_is_held(self) -> None:
        # Nothing published: no push, no pull request, and the label handed to
        # the adjudication rather than to review.
        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_held(mocks)
        self.assertEqual(self.github.label_history, [_DECOMPOSING])

    def test_the_hold_records_what_it_measured(self) -> None:
        # The record the coordinator is handed names both commits, the ceiling
        # they were measured under, the boundary they stand at, and the
        # identities every later record is correlated by -- because that record
        # is the whole of what the adjudication reconciles from.
        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_frozen(additions=support.OVERSIZED_ADDITIONS)
        pinned = self._pinned()
        self.assertEqual(pinned[support.KEY_THRESHOLD], config.MAX_ADDED_LINES)
        self.assertEqual(pinned[support.KEY_CYCLE_ID], 1)
        self.assertEqual(pinned[support.KEY_GENERATION], 1)
        self.assertEqual(
            pinned[support.KEY_CURRENT_ISSUE], support.GATE_ISSUE_NUMBER,
        )
        self.assertEqual(
            pinned[support.KEY_ROOT_ISSUE], support.GATE_ISSUE_NUMBER,
        )
        self.assertEqual(pinned[support.KEY_LINEAGE_DEPTH], 0)

    def test_the_hold_records_no_publication(self) -> None:
        # An initial publication is the side of the gate that has no pull
        # request behind it, and the record says so by carrying none of the
        # publication group -- which is what lets a live pinned comment answer
        # the question with no migration having reached it.
        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        pinned = self._pinned()
        for absent in (
            _POST_PUBLICATION, _SOURCE_STAGE, _PUBLISHED_PR, _PUBLISHED_SHA,
        ):
            self.assertNotIn(absent, pinned)

    def test_the_hold_says_what_it_waits_for(self) -> None:
        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        notice = self.github.posted_comments[-1][1]
        self.assertIn(str(support.OVERSIZED_ADDITIONS), notice)
        self.assertIn(str(config.MAX_ADDED_LINES), notice)
        self.assertIn(MEASURED_CANDIDATE_SHA, notice)

    def test_a_candidate_at_the_ceiling_publishes(self) -> None:
        # Strictly past, so the trigger cannot move by one line when the
        # threshold is retuned.
        mocks = self._run_gate(added_lines=config.MAX_ADDED_LINES)

        self._assert_published(mocks)


class LateGateRetirementTest(support._GateCase, unittest.TestCase):
    """A retirement is durable before the publication it licenses.

    What follows one is a push, a pull request, and the label that hands the
    issue to review -- and the tick's own pinned write comes after all of it.
    A crash in that window would leave a published pull request under
    `workflow:validating` over a record that still says `measuring`: the
    branch frozen out of the base refresh for good, and a close on that issue
    read by the cancellation guard as a live cycle to end.
    """

    def test_a_small_candidate_retires_first(self) -> None:
        recorded = support._RecordAtHandoff(self.github)

        with recorded.held():
            self._run_gate(added_lines=support.SMALL_ADDITIONS)

        self.assertNotIn(support.KEY_CANDIDATE_SHA, recorded.pinned)
        self.assertEqual(recorded.pinned[support.KEY_RETIRED_CYCLE], 1)


class LateGatePushTest(support._GateCase, unittest.TestCase):
    """The push is named against the commit that passed, not against HEAD.

    The gate reads the checkout and the publication writes it, and `HEAD`
    between those two moments is not necessarily the commit that passed:
    another tick, an operator, or a descendant the timeout cleanup raced can
    move it. A push that named nothing would publish whatever it had become
    while the record named the commit that was measured.
    """

    def test_the_measured_commit_is_pushed(self) -> None:
        mocks = self._run_gate(added_lines=support.SMALL_ADDITIONS)

        self.assertEqual(
            mocks[support.PUSH_BRANCH].call_args.kwargs["revision"],
            MEASURED_CANDIDATE_SHA,
        )

    def test_the_exempt_commit_is_pushed(self) -> None:
        self._seed(**{support.KEY_EXEMPT_SHA: MEASURED_CANDIDATE_SHA})

        mocks = self._run_gate()

        self.assertEqual(
            mocks[support.PUSH_BRANCH].call_args.kwargs["revision"],
            MEASURED_CANDIDATE_SHA,
        )

    def test_a_moved_checkout_publishes_nothing(self) -> None:
        # The push would be safe on its own -- it names the approved commit --
        # but the CHECKOUT is what every stage past this one works from: the
        # reviewer reads a head ahead of the pushed branch as unpushed work to
        # publish, the squash rewrites what is on it, and the docs pass commits
        # on top. A worktree left on a descendant would carry an implementation
        # the gate never saw into review, a merge later.
        mocks = self._run_gate(
            added_lines=support.SMALL_ADDITIONS,
            candidate_commit=_MOVING_HEAD,
        )

        self._assert_held(mocks)
        self.assertEqual(self.github.label_history, [])
        pinned = self._pinned()
        self.assertTrue(pinned[support.AWAITING_HUMAN])
        self.assertEqual(pinned[support.PARK_REASON], _CANDIDATE_MOVED)

    def test_a_moved_checkout_says_both_commits(self) -> None:
        self._run_gate(
            added_lines=support.SMALL_ADDITIONS,
            candidate_commit=_MOVING_HEAD,
        )

        notice = self.github.posted_comments[-1][1]
        self.assertIn(MEASURED_CANDIDATE_SHA, notice)
        self.assertIn(_OTHER_SHA, notice)

    def test_an_unmeasured_branch_is_named_too(self) -> None:
        # The switch keeps a candidate out of the MEASUREMENT; it does not
        # make it unnameable. A push named against nothing publishes whatever
        # the branch has become by the time git runs it, and leaves nothing on
        # the issue afterwards saying which commit that was -- so the checkout
        # names it where the gate did not.
        with patch.object(config, _DECOMPOSE, False):
            mocks = self._run_gate()

        self._assert_unmeasured(mocks)
        self.assertEqual(
            mocks[support.PUSH_BRANCH].call_args.kwargs["revision"],
            MEASURED_CANDIDATE_SHA,
        )


class LateGateTelemetryTest(support._GateCase, unittest.TestCase):
    """One call, two streams, and a record that joins without pinned state."""

    def test_the_audit_stream_carries_it(self) -> None:
        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        measured = self._records(support.EVENT_LATE_MEASUREMENT)
        self.assertEqual(len(measured), 1)
        self._assert_record(measured[0], support.OVERSIZED_ADDITIONS)

    def test_the_analytics_stream_carries_it(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            log_path = Path(scratch) / "analytics.jsonl"
            self._run_gate(
                added_lines=support.SMALL_ADDITIONS,
                analytics_log_path=log_path,
            )
            recorded = [
                record for record in _analytics_records(log_path)
                if record.get("event") == support.EVENT_LATE_MEASUREMENT
            ]

        self.assertEqual(len(recorded), 1)
        self._assert_record(recorded[0], support.SMALL_ADDITIONS)

    def _assert_record(self, record: dict, additions: int) -> None:
        self.assertEqual(record["stage"], _STAGE_IMPLEMENTING)
        self.assertEqual(record["issue"], support.GATE_ISSUE_NUMBER)
        self.assertEqual(record["source_sha"], MEASURED_CANDIDATE_SHA)
        self.assertEqual(record["base_sha"], MEASURED_BASE_SHA)
        self.assertEqual(record["additions"], additions)
        self.assertEqual(record["threshold"], config.MAX_ADDED_LINES)
        self.assertEqual(record["cycle_id"], 1)
        self.assertEqual(record["root_issue"], support.GATE_ISSUE_NUMBER)


class LateGateExemptionTest(support._ParkedRetryCase, unittest.TestCase):
    """The one commit an adjudication accepted, and nothing beside it."""

    def test_an_exemption_retires_the_record(self) -> None:
        # A guidance resume can put the checkout back on a commit an
        # adjudication already accepted, while the record still names the
        # candidate that resume was about. Publishing the exemption without
        # dropping that record would leave a generation pinned at `measuring`
        # over work nothing is going to publish -- freezing the branch out of
        # the base refresh and carrying a live-looking cycle into the stages
        # that close the issue.
        mocks = self._resumed_onto_the_exemption()

        self._assert_unmeasured(mocks)
        self._assert_published(mocks)
        pinned = self._pinned()
        self.assertNotIn(support.KEY_CANDIDATE_SHA, pinned)
        self.assertEqual(pinned[support.KEY_RETIRED_CYCLE], 1)

    def test_an_exemption_retires_before_the_push(self) -> None:
        recorded = support._RecordAtHandoff(self.github)

        with recorded.held():
            self._resumed_onto_the_exemption()

        self.assertNotIn(support.KEY_CANDIDATE_SHA, recorded.pinned)
        self.assertEqual(recorded.pinned[support.KEY_RETIRED_CYCLE], 1)

    def test_an_accepted_commit_is_not_measured(self) -> None:
        # Without this the gate would measure the accepted candidate past the
        # same ceiling and adjudicate it again, forever.
        self._seed(**{support.KEY_EXEMPT_SHA: MEASURED_CANDIDATE_SHA})

        mocks = self._run_gate()

        self._assert_unmeasured(mocks)
        self._assert_published(mocks)

    def test_work_past_it_is_a_fresh_candidate(self) -> None:
        self._seed(**{support.KEY_EXEMPT_SHA: _OTHER_SHA})

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_held(mocks)

    def _resumed_onto_the_exemption(self):
        """A resume that put the checkout back on an accepted commit.

        The record names the candidate the guidance was about; the checkout
        ends on the commit an earlier adjudication accepted. Both are true at
        once, which is the coexistence this subject is about.
        """
        self._seed(**{
            support.AWAITING_HUMAN: True,
            support.PARK_REASON: support.PARK_MEASUREMENT_FAILED,
            support.LAST_ACTION_COMMENT_ID: support.PRIOR_ACTION_COMMENT_ID,
            "dev_agent": "codex",
            "dev_session_id": support.DEV_SESSION,
            support.KEY_EXEMPT_SHA: MEASURED_CANDIDATE_SHA,
            **support.recorded_generation(candidate_sha=_OTHER_SHA),
        })
        self._reply("put it back on the commit we already agreed")
        return self._run_gate(
            run_agent=_agent(
                session_id=support.DEV_SESSION, last_message="reset",
            ),
            head_shas=(_OTHER_SHA, MEASURED_CANDIDATE_SHA),
        )


class LateGateSwitchTest(support._GateCase, unittest.TestCase):
    """`DECOMPOSE=off` keeps new work out, and decides nothing already in."""

    def test_a_new_candidate_is_not_measured(self) -> None:
        # Nothing is decided about it and nothing is recorded for it: the
        # switch keeps a candidate out of the gate rather than answering the
        # gate's question cheaply, so the issue leaves carrying no generation
        # at all.
        with patch.object(config, _DECOMPOSE, False):
            mocks = self._run_gate()

        self._assert_unmeasured(mocks)
        self._assert_published(mocks)
        self.assertNotIn(support.KEY_CYCLE_ID, self._pinned())

    def test_a_recorded_one_is_reconciled(self) -> None:
        # The switch decides whether work ENTERS the gate. A candidate this
        # issue already froze is in it, and turning the switch off must not
        # publish it as though a verdict had been recorded for it.
        self._seed(**support.recorded_generation())

        with patch.object(config, _DECOMPOSE, False):
            mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_held(mocks)
        self.assertIn(_DECOMPOSING, self.github.label_history)


if __name__ == "__main__":
    unittest.main()
