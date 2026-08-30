# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a verdict the owner read cleared actually earns, and what it does not.

A `single` is an exemption for one commit and a hand-back to the ordinary
publication; a `split` is a handoff to the transaction that creates its
children; a `question` is neither. None of the three creates a snapshot here.

The plan-PR hold is the other half of the same pull request, so what it left
standing is asked here too: a notice a human removed is what stops a new agent
being started under an open change, and is exactly what may not stop an answer
already recorded from settling.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.workflow.late_split import exemption as _exemption
from orchestrator.workflow.late_split.models import LateFailure
from orchestrator.workflow.stages.decomposition.late_models import (
    _LateDisposition,
)

from tests.workflow.fixtures import LABEL_DECOMPOSING, LABEL_IMPLEMENTING
from tests.workflow.stages.decomposition.late_settlement_support import (
    ERROR,
    EVENT_LATE_SNAPSHOT,
    GuardedLateCase,
    HUMAN_REWRITE,
    HeldPlanPrCase,
    PARK_HOLD_FAILED,
    SPLIT_CHILDREN,
    WORKFLOW_LOG,
)
from tests.workflow.stages.decomposition.late_settlement_support import (
    HUMAN_ADDITION,
    QUESTION_RUN,
    SINGLE_RUN,
    SPLIT_RUN,
    _ClosedDuringRun,
    _RewrittenDuringRun,
)
from tests.workflow.stages.decomposition.late_test_support import (
    ADDITIONS,
    CANDIDATE_SHA,
    EVENT_LATE_FAILURE,
    HOLD_MARKER_PREFIX,
    KEYS,
    OTHER_SHA,
)
from tests.workflow.stages.decomposition.late_test_support import (
    PLAN_PR_BODY,
    PLAN_PR_NUMBER,
)
from tests.workflow.stages.decomposition.late_test_support import (
    generation_state,
    late_generation,
)

EDIT_PR_BODY = "edit_pr_body"

PR_CLOSED = "closed"

PR_NUMBER = "pr_number"


ACCEPTED_NOTICE = "one coherent change"

# What a settled generation leaves behind on the pinned comment: none of it.
_RETIRED_KEYS = (
    KEYS.candidate_sha,
    KEYS.base_sha,
    KEYS.phase,
    KEYS.plan_pr_number,
    KEYS.plan_pr_body,
    KEYS.resources,
)


class SingleReconciliationTest(GuardedLateCase, unittest.TestCase):
    """An accepted candidate publishes as itself, and only as itself."""

    def test_the_measured_commit_is_exempted(self) -> None:
        outcome = self._decide(SINGLE_RUN)

        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(self._pinned().get(KEYS.exempt_sha), CANDIDATE_SHA)
        self.assertEqual(
            self.github.workflow_label(self.issue), LABEL_IMPLEMENTING,
        )
        said = self.github.posted_comments[-1][1]
        self.assertIn(ACCEPTED_NOTICE, said)
        self.assertIn(str(ADDITIONS), said)

    def test_the_accepted_commit_is_owed_a_push(self) -> None:
        # The exemption says the commit needs no measuring; it does not say
        # the issue is still waiting for it to be pushed -- and the retirement
        # a line later takes away the record that did. Without this pair, a
        # replacement host picking the issue up under `implementing` would
        # rebuild the checkout from the base or the plan PR and publish that
        # head instead, or pay for a second developer over an implementation a
        # human has already ruled on.
        self._decide(SINGLE_RUN)

        self.assertEqual(self._pinned().get(KEYS.approved_sha), CANDIDATE_SHA)

    def test_the_generation_it_settles_is_retired(self) -> None:
        # Left standing, it would keep pinning the decomposing label and keep
        # reading as a candidate nobody has decided about.
        self._decide(SINGLE_RUN)

        pinned = self._pinned()
        for retired in _RETIRED_KEYS:
            with self.subTest(key=retired):
                self.assertNotIn(retired, pinned)

    def test_it_creates_no_snapshot_or_children(self) -> None:
        # A snapshot exists so children can be cut from a candidate about to
        # be superseded. An accepted candidate supersedes nothing.
        self._decide(SINGLE_RUN)

        self.assertEqual(self._events_named(EVENT_LATE_SNAPSHOT), [])
        self.assertEqual(self.github.created_child_issues, [])
        self.assertNotIn(KEYS.resources, self._pinned())

    def test_only_the_measured_commit_is_exempt(self) -> None:
        # The invalidation rule, read where the gate reads it: anything
        # committed on top of the accepted candidate is a fresh candidate.
        self._decide(SINGLE_RUN)
        state = self.github.read_pinned_state(self.issue)

        self.assertTrue(_exemption.is_exempt(state, CANDIDATE_SHA))
        self.assertFalse(_exemption.is_exempt(state, OTHER_SHA))

    def test_a_half_finished_settlement_finishes(self) -> None:
        # The window a crash can land in: the exemption is durable and the
        # hold is already off, but the label was never handed on. The retry
        # reuses the recorded answer and settles the rest.
        self.github.seed_state(self.issue.number, **_half_settled_state())

        outcome, spawn = self._adjudicate()

        spawn.assert_not_called()
        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(
            self.github.workflow_label(self.issue), LABEL_IMPLEMENTING,
        )
        self.assertEqual(self._pinned().get(KEYS.exempt_sha), CANDIDATE_SHA)



class WithheldExemptionTest(GuardedLateCase, unittest.TestCase):
    """An owner the guard could not clear exempts nothing."""

    def test_a_closed_owner_exempts_nothing(self) -> None:
        outcome = self._decide(_ClosedDuringRun(self.issue, SINGLE_RUN))

        self.assertEqual(outcome.disposition, _LateDisposition.CANCELLED)
        self._assert_nothing_published()

    def test_an_unreadable_owner_exempts_nothing(self) -> None:
        outcome = self._decide_unread(SINGLE_RUN)

        self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
        self._assert_nothing_published()

    def _assert_nothing_published(self) -> None:
        """No exemption and no hand-back, so the gate still owns the issue."""
        self.assertNotIn(KEYS.exempt_sha, self._pinned())
        self.assertEqual(
            self.github.workflow_label(self.issue), LABEL_DECOMPOSING,
        )


class DisplacedHoldTest(HeldPlanPrCase, unittest.TestCase):
    """A notice a human removed stops the next agent, not the settlement.

    Their words are left where they wrote them either way. What differs is
    what may run under the pull request afterwards: nothing new, since it is
    now open with nothing on it saying an adjudication is running, while an
    answer already recorded may still be settled -- settling releases a hold
    that is already gone.
    """

    def test_a_displaced_hold_spawns_nothing(self) -> None:
        # The crash-after-hold window: the hold landed, the tick died before a
        # verdict, and a human rewrote the description before the retry.
        self.plan_pr.body = HUMAN_REWRITE

        outcome, spawn = self._adjudicate(SINGLE_RUN)

        spawn.assert_not_called()
        self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
        self.assertEqual(self._pinned().get(KEYS.park_reason), PARK_HOLD_FAILED)
        self.assertEqual(self.plan_pr.body, HUMAN_REWRITE)
        self.assertEqual(self.github.edited_pr_bodies, [])

    def test_the_refusal_is_recorded_and_said_once(self) -> None:
        self.plan_pr.body = HUMAN_REWRITE
        self._adjudicate(SINGLE_RUN)

        self._adjudicate(SINGLE_RUN)

        self.assertEqual(
            self._events_named(EVENT_LATE_FAILURE)[-1].get("failure"),
            LateFailure.PLAN_PR_HOLD_FAILED,
        )
        self.assertEqual(len(self.github.posted_comments), 1)

    def test_a_settled_pr_spawns_as_it_would_have(self) -> None:
        # Only an OPEN pull request is one a human could merge under, so a
        # rewritten description on one they have already closed stops nothing.
        self.plan_pr.body = HUMAN_REWRITE
        self.plan_pr.state = PR_CLOSED

        outcome, spawn = self._adjudicate(SINGLE_RUN)

        spawn.assert_called_once()
        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)


class ReleasedHoldTest(HeldPlanPrCase, unittest.TestCase):
    """The description a hold replaced goes back before anything publishes."""

    def test_the_preserved_description_is_restored(self) -> None:
        self._decide(SINGLE_RUN)

        self.assertEqual(self.plan_pr.body, PLAN_PR_BODY)
        self.assertNotIn(HOLD_MARKER_PREFIX, self.plan_pr.body)
        self.assertEqual(
            self.github.edited_pr_bodies[-1], (PLAN_PR_NUMBER, PLAN_PR_BODY),
        )

    def test_a_rewritten_description_is_left_alone(self) -> None:
        # The preserved copy describes a body that is no longer there, and the
        # words that are there belong to whoever wrote them.
        rewritten = _RewrittenDuringRun(self.plan_pr, SINGLE_RUN)

        outcome = self._decide(rewritten)

        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(self.plan_pr.body, HUMAN_REWRITE)

    def test_an_edited_hold_is_not_overwritten(self) -> None:
        # The marker is hidden, so a human editing one sentence of the notice
        # leaves it in place. Restoring on the strength of that would put the
        # preserved copy back over what they actually wrote.
        edited = _RewrittenDuringRun(
            self.plan_pr, SINGLE_RUN, self.plan_pr.body + HUMAN_ADDITION,
        )

        outcome = self._decide(edited)

        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertIn(HOLD_MARKER_PREFIX, self.plan_pr.body)
        self.assertIn(HUMAN_ADDITION, self.plan_pr.body)
        self.assertNotIn(PLAN_PR_BODY, self.plan_pr.body)
        self.assertEqual(self.github.edited_pr_bodies, [])

    def test_a_settled_pull_request_gets_it_back(self) -> None:
        # A human merging or closing the plan PR decided something about that
        # pull request, not about the commit -- and leaving "do not merge" on
        # a description nothing is adjudicating any more helps nobody.
        self.plan_pr.merged = True
        self.plan_pr.state = PR_CLOSED

        self._decide(SINGLE_RUN)

        self.assertEqual(self.plan_pr.body, PLAN_PR_BODY)
        self.assertEqual(self._pinned().get(KEYS.exempt_sha), CANDIDATE_SHA)

    def test_a_rewrite_survives_a_recovered_verdict(self) -> None:
        # The composition: a verdict recorded durably, an owner read that did
        # not come back, and a human replacing the held description before the
        # retry. The retry must not re-hold what they wrote -- doing so would
        # make the release believe those words were this generation's and put
        # the stale original back over them.
        self._decide_unread(SINGLE_RUN)
        self.plan_pr.body = HUMAN_REWRITE

        outcome, spawn = self._adjudicate()

        spawn.assert_not_called()
        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(self.plan_pr.body, HUMAN_REWRITE)
        self.assertEqual(self.github.edited_pr_bodies, [])

    def test_a_failed_edit_on_a_settled_pr_publishes(self) -> None:
        # What parking on a failed release is for is a change somebody can
        # still merge while it wears a notice saying not to. A pull request a
        # human already settled is not that, so an edit GitHub refuses on one
        # is untidy and nothing more -- blocking an adjudicated candidate on
        # it would be a permanent stop bought for nothing.
        self.plan_pr.merged = True
        self.plan_pr.state = PR_CLOSED
        refused = patch.object(
            self.github, EDIT_PR_BODY, side_effect=RuntimeError,
        )

        with refused:
            with self.assertLogs(WORKFLOW_LOG, level=ERROR):
                outcome = self._decide(SINGLE_RUN)

        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(self._pinned().get(KEYS.exempt_sha), CANDIDATE_SHA)
        self.assertEqual(
            self.github.workflow_label(self.issue), LABEL_IMPLEMENTING,
        )

    def test_a_failed_release_publishes_nothing(self) -> None:
        # The pull request is open, so the hold it still wears is a "do not
        # merge" standing on a change a human can merge.
        refused = patch.object(
            self.github, EDIT_PR_BODY, side_effect=RuntimeError,
        )

        with refused:
            with self.assertLogs(WORKFLOW_LOG, level=ERROR):
                outcome = self._decide(SINGLE_RUN)

        self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
        pinned = self._pinned()
        self.assertEqual(pinned.get(KEYS.park_reason), PARK_HOLD_FAILED)
        self.assertNotIn(KEYS.exempt_sha, pinned)
        # The generation is untouched, which is what makes the retry free.
        self.assertEqual(pinned.get(KEYS.candidate_sha), CANDIDATE_SHA)
        self.assertEqual(
            self.github.workflow_label(self.issue), LABEL_DECOMPOSING,
        )


class GuardedSplitTest(GuardedLateCase, unittest.TestCase):
    """A split reaches the transaction only with an owner read behind it."""

    def test_a_cleared_split_carries_its_manifest(self) -> None:
        outcome = self._decide(SPLIT_RUN)

        self.assertEqual(outcome.disposition, _LateDisposition.DECIDED)
        handed = outcome.guarded_split
        self.assertEqual(len(handed.children), SPLIT_CHILDREN)
        self.assertEqual(handed.generation.candidate_sha, CANDIDATE_SHA)
        # Handing it on is all that happens here: creating the children and
        # superseding the plan PR are one transaction of their own.
        self.assertEqual(self.github.created_child_issues, [])
        self.assertEqual(self.github.label_history, [])

    def test_a_closed_owner_hands_no_split_on(self) -> None:
        outcome = self._decide(_ClosedDuringRun(self.issue, SPLIT_RUN))

        self.assertIsNone(outcome.guarded_split)
        self.assertEqual(self.github.created_child_issues, [])

    def test_an_unread_owner_hands_no_split_on(self) -> None:
        outcome = self._decide_unread(SPLIT_RUN)

        self.assertIsNone(outcome.guarded_split)
        self.assertEqual(self.github.created_child_issues, [])


class QuestionSettlementTest(GuardedLateCase, unittest.TestCase):
    """A categorized question earns an announcement and nothing else."""

    def test_it_settles_nothing(self) -> None:
        outcome = self._decide(QUESTION_RUN)

        self.assertEqual(outcome.disposition, _LateDisposition.DECIDED)
        pinned = self._pinned()
        self.assertNotIn(KEYS.exempt_sha, pinned)
        self.assertEqual(self.github.label_history, [])
        self.assertEqual(pinned.get(KEYS.candidate_sha), CANDIDATE_SHA)


def _half_settled_state() -> dict:
    """The pinned comment a crash between the exemption and the label left."""
    return {
        **generation_state(late_generation()),
        KEYS.verdict: "single",
        KEYS.run_cycle_id: late_generation().cycle_id,
        KEYS.run_generation: late_generation().generation,
        KEYS.source_sha: CANDIDATE_SHA,
        KEYS.exempt_sha: CANDIDATE_SHA,
    }


if __name__ == "__main__":
    unittest.main()
