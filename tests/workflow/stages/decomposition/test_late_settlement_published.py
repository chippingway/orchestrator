# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A `single` verdict taken over a pull request the remote already carries.

The reading a `single` accepts is a claim about what THAT pull request would
come to with the candidate in it, so what the settlement owes before it
publishes is a proof that the pull request is still the one the claim was
about -- readable, open, and standing where the reading found it -- and then
the push itself, made from here because this is the last tick holding the
evidence. The pre-publication side of the same verdict is in
`test_late_settlement.py`.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.workflow.stages.decomposition.late_models import (
    _LateDisposition,
)
from tests.support.fakes import LazyPullRequest
from tests.workflow.fixtures import LABEL_DECOMPOSING
from tests.workflow.stages.decomposition.late_published_support import (
    published_generation,
    seed_published_pr,
)
from tests.workflow.stages.decomposition.late_run_support import WorktreeSeed
from tests.workflow.stages.decomposition.late_settlement_support import (
    PARK_HOLD_FAILED,
    PARK_PR_UNRECONCILED,
    SINGLE_RUN,
    GuardedLateCase,
)
from tests.workflow.stages.decomposition.late_test_support import (
    CANDIDATE_SHA,
    KEYS,
    OTHER_SHA,
    PUBLISHED_HEAD_SHA,
    PUBLISHED_PR_NUMBER,
    PUBLISHED_SOURCE_STAGE,
    PUBLISHED_SOURCE_STAGES,
    generation_state,
)

EDIT_PR_BODY = "edit_pr_body"

PR_CLOSED = "closed"

PR_NUMBER = "pr_number"
SET_WORKFLOW_LABEL = "set_workflow_label"
LABEL_WRITE_REJECTED = "label write rejected"


def _CRASHES(*_called, **_options):
    """The label write a settled verdict dies on, past its own push."""
    raise RuntimeError(LABEL_WRITE_REJECTED)


class _RefusingMidRun:
    """A finished run that leaves the publication refusing one lazy read.

    Installed from inside the spawn rather than from the seed, because the
    hold this tick takes reads the same pull request before the agent starts:
    a fixture refusing from the first request would stop the tick there and
    never reach the settlement at all.
    """

    def __init__(self, github, failing: str) -> None:
        self._github = github
        self._failing = failing

    def __call__(self, *_called, **_options):
        self._github.add_pr(LazyPullRequest(
            self._github.get_pr(PUBLISHED_PR_NUMBER), failing=self._failing,
        ))
        return SINGLE_RUN

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


class _PublishedVerdictMixin:
    """The seed and the readings one post-publication verdict is decided by."""

    def _seed_settled(self, *, published: bool = True) -> None:
        """The pinned comment a crash left, with the verdict already read."""
        if published:
            seed_published_pr(self.github)
        self.github.seed_state(self.issue.number, **{
            **generation_state(published_generation()),
            KEYS.verdict: "single",
            KEYS.run_cycle_id: published_generation().cycle_id,
            KEYS.run_generation: published_generation().generation,
            KEYS.source_sha: CANDIDATE_SHA,
            KEYS.exempt_sha: CANDIDATE_SHA,
        })

    def _label(self):
        """The workflow label this issue is wearing now."""
        return self.github.workflow_label(self.issue)

    def _seed_published(self, *, stage=None, **pr_fields) -> None:
        """Re-seed this issue as one whose verdict was taken past publication."""
        seed_published_pr(self.github, **pr_fields)
        entered = (
            published_generation(stage=stage) if stage
            else published_generation()
        )
        self.github.seed_state(
            self.issue.number, **generation_state(entered),
        )

    def _assert_unpublished(self, outcome) -> None:
        """Nothing handed on, and the record left for the next tick to read."""
        self.assertNotEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(self._label(), LABEL_DECOMPOSING)
        pinned = self._pinned()
        self.assertEqual(pinned.get(KEYS.park_reason), PARK_PR_UNRECONCILED)
        self.assertEqual(pinned.get(KEYS.candidate_sha), CANDIDATE_SHA)


class PublishedSingleReconciliationTest(
    GuardedLateCase, _PublishedVerdictMixin, unittest.TestCase,
):
    """Where a verdict taken past publication puts the commit it accepted.

    The push belongs to the settlement because the settlement is the last tick
    holding the evidence, and the label goes to the stage the record names
    rather than back to `implementing`.
    """

    def test_it_publishes_onto_the_frozen_publication(self) -> None:
        # The push belongs to this tick because only this tick still holds the
        # evidence: the verdict was taken against one pull request standing on
        # one head, and the retirement a line later takes the record that said
        # so away. Landed, the debt it was recorded under is paid.
        self._seed_published()

        outcome = self._decide(SINGLE_RUN)

        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        pinned = self._pinned()
        self.assertEqual(pinned.get(PR_NUMBER), PUBLISHED_PR_NUMBER)
        self.assertIsNone(pinned.get(KEYS.approved_sha))
        self.assertIsNone(pinned.get(KEYS.approved_lease))

    def test_it_continues_at_the_stage_it_came_from(self) -> None:
        # The stage the gate took the issue out of is the only owner of the
        # completion the candidate still owes -- a docs watermark and its
        # `in_review` handoff, a conflict round, another reviewer look. Sending
        # it to `implementing` instead walks the issue back to a point it had
        # already passed.
        self._seed_published()

        self._decide(SINGLE_RUN)

        self.assertEqual(self._label(), PUBLISHED_SOURCE_STAGE)

    def test_every_source_stage_is_continued_at(self) -> None:
        # The five states the gate can take an issue out of are the five it
        # can put one back into, and each is the only owner of the completion
        # its candidate still owes.
        for stage in PUBLISHED_SOURCE_STAGES:
            with self.subTest(stage=stage):
                self.setUp()
                self._seed_published(stage=stage)

                self._decide(SINGLE_RUN)

                self.assertEqual(self._label(), stage)

    def test_a_landed_push_finishes_its_tick(self) -> None:
        # The push happens before the relabel and the retirement, so a tick
        # that dies in between comes back to a live generation over a pull
        # request the commit is already on. Read as external movement, the one
        # publication refused forever would be the one this verdict made.
        self._seed_published()
        with patch.object(self.github, SET_WORKFLOW_LABEL, _CRASHES), self.assertRaises(RuntimeError):
            self._decide(SINGLE_RUN)
        # The push landed before the label write died, so the pull request is
        # standing on the accepted candidate when the retry looks.
        self.github.get_pr(PUBLISHED_PR_NUMBER).head.sha = CANDIDATE_SHA

        outcome, spawn = self._adjudicate(worktree=WorktreeSeed(push=False))

        spawn.assert_not_called()
        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(self._label(), PUBLISHED_SOURCE_STAGE)
        pinned = self._pinned()
        # Nothing is owed: pushing again would be a second push of a commit
        # that is already there, and a debt on the record freezes this branch
        # out of the base refresh for the rest of the issue's life.
        self.assertIsNone(pinned.get(KEYS.approved_sha))
        self.assertIsNone(pinned.get(KEYS.approved_lease))

    def test_a_push_that_missed_keeps_the_verdict(self) -> None:
        # A refused push here is usually the lease doing its job. The verdict
        # is durable, so the retry asks for the same commit against the same
        # head rather than handing a stage a pull request that never got it.
        self._seed_published()

        outcome = self._decide(SINGLE_RUN, worktree=WorktreeSeed(push=False))

        self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
        self.assertEqual(self._label(), LABEL_DECOMPOSING)
        pinned = self._pinned()
        self.assertEqual(pinned.get(KEYS.approved_sha), CANDIDATE_SHA)
        self.assertEqual(pinned.get(KEYS.approved_lease), PUBLISHED_HEAD_SHA)
        self.assertEqual(pinned.get(KEYS.park_reason), PARK_PR_UNRECONCILED)

    def test_a_settled_publication_is_refused(self) -> None:
        # Dropping the number here -- what a pre-publication verdict rightly
        # does with a stale pointer -- would push onto a branch whose pull
        # request a human settled and open a second one for a change that was
        # adjudicated against the first.
        self._seed_published(pr_state=PR_CLOSED)

        outcome = self._decide(SINGLE_RUN)

        self._assert_unpublished(outcome)


class PublishedCheckoutProofTest(
    GuardedLateCase, _PublishedVerdictMixin, unittest.TestCase,
):
    """The checkout a settled verdict may hand its stage, and what fails it.

    What a human accepted is one commit with nothing loose beside it, and the
    worktree it was accepted from is writable through the whole adjudication,
    through the push itself, and through the tick that died between a landed
    push and the retry that finishes it. Every stage the label is about to
    hand this issue to works from that checkout.
    """

    def test_a_mutated_checkout_keeps_the_verdict(self) -> None:
        # A recorded verdict settles with no run behind it, so the read-only
        # proof a finished run passes does not run again -- and an
        # adjudication is a human reading a diff over hours, with the worktree
        # writable the whole time. Every stage past this one works from the
        # CHECKOUT, so one left on an unmeasured descendant would reach
        # review, a squash, and a merge with nobody having read it, even
        # though the push itself names the accepted id.
        for mutation in (
            WorktreeSeed(head=OTHER_SHA),
            WorktreeSeed(dirty=("scratch.txt",)),
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self._seed_settled()

                outcome, spawn = self._adjudicate(worktree=mutation)

                spawn.assert_not_called()
                self._assert_unpublished(outcome)

    def test_a_push_that_moved_it_holds_the_handoff(self) -> None:
        # The window the pre-push proof cannot cover: a push is a request and
        # the worktree is writable for the whole of it. What went out is the
        # accepted commit, so the pull request is right; what is wrong is the
        # CHECKOUT, and every stage the label is about to hand this issue to
        # works from that -- the reviewer reads a head ahead of the pushed
        # branch as unpublished work, the squash rewrites what is on it.
        for mutation in (
            WorktreeSeed(head_after_push=OTHER_SHA),
            WorktreeSeed(dirty_after_push=("scratch.txt",)),
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self._seed_published()

                outcome = self._decide(SINGLE_RUN, worktree=mutation)

                self._assert_unpublished(outcome)

    def test_a_landed_retry_proves_the_checkout(self) -> None:
        # A retry finishing a settlement whose own push landed makes no push
        # of its own, so nothing in it would read the checkout -- and the
        # worktree has been writable since the process that pushed died. The
        # commit is on the pull request either way; what may not be handed on
        # is a checkout carrying loose edits or an unmeasured descendant.
        for mutation in (
            WorktreeSeed(head=OTHER_SHA),
            WorktreeSeed(dirty=("scratch.txt",)),
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                self._seed_landed_push()

                outcome, spawn = self._adjudicate(worktree=mutation)

                spawn.assert_not_called()
                self._assert_unpublished(outcome)

    def _seed_landed_push(self) -> None:
        """Leave the settlement whose own push landed and whose tick died."""
        self._seed_published()
        with patch.object(self.github, SET_WORKFLOW_LABEL, _CRASHES), self.assertRaises(RuntimeError):
            self._decide(SINGLE_RUN)
        self.github.get_pr(PUBLISHED_PR_NUMBER).head.sha = CANDIDATE_SHA


class PublishedVerdictRefusalTest(
    GuardedLateCase, _PublishedVerdictMixin, unittest.TestCase,
):
    """Every proof the settlement owes before it publishes, and what fails it.

    The reading a `single` accepts is a claim about ONE pull request standing
    on one head, so a publication that cannot be read, has been settled, or
    has moved is not the one the verdict was about -- and the candidate is
    left for a tick that can prove it rather than pushed on a claim that has
    been overtaken.
    """

    def test_a_state_nothing_could_read_is_refused(self) -> None:
        # A fetched pull request asks GitHub nothing, so the request that
        # fails is an attribute read behind the lookup -- and the settlement
        # meets it taking this cycle's hold back off the same pull request,
        # one step ahead of the proof. Left to raise, the tick would end with
        # the branch still carrying the accepted candidate and nothing on the
        # thread saying why.
        self._seed_published()

        outcome = self._decide(_RefusingMidRun(self.github, "state"))

        self._assert_unreleased(outcome)

    def test_a_head_nothing_could_read_is_refused(self) -> None:
        # The other lazy read, refused for the same reason: neither the
        # description this generation displaced nor the candidate it accepted
        # may be acted on through a pull request nobody could read.
        self._seed_published()

        outcome = self._decide(_RefusingMidRun(self.github, "head"))

        self._assert_unreleased(outcome)

    def test_a_moved_publication_is_refused(self) -> None:
        # Something pushed to it during the adjudication, so what the verdict
        # was taken over is not what the branch would come to.
        self._seed_published(head=OTHER_SHA)

        outcome = self._decide(SINGLE_RUN)

        self._assert_unpublished(outcome)

    def test_a_pre_publication_verdict_pins_nothing(self) -> None:
        # A verdict taken before anything was published names no pull
        # request to have been measured against, so its push reads the remote
        # for itself rather than being pinned to a frozen head.
        self._decide(SINGLE_RUN)

        self.assertIsNone(self._pinned().get(KEYS.approved_lease))

    def _assert_unreleased(self, outcome) -> None:
        """Nothing handed on, and the hold left for the next tick to retry."""
        self.assertNotEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(self._label(), LABEL_DECOMPOSING)
        pinned = self._pinned()
        self.assertEqual(pinned.get(KEYS.park_reason), PARK_HOLD_FAILED)
        self.assertEqual(pinned.get(KEYS.candidate_sha), CANDIDATE_SHA)


class PublishedOwnPushTest(
    GuardedLateCase, _PublishedVerdictMixin, unittest.TestCase,
):
    """The one moved head this road forgives, and what it takes to earn it.

    A pull request standing on the accepted candidate is this settlement's own
    push having landed on a tick that died before the label behind it -- but
    only where a DURABLE record says so, and the commit is not one. This call
    runs ahead of the exemption, the approval, and the push, so on a fresh
    pass nothing of this workflow's has reached the remote at all.
    """

    def test_a_move_onto_the_candidate_is_refused(self) -> None:
        # The exact-candidate move on a FRESH pass, which is the one the
        # commit alone cannot explain. This call runs ahead of the exemption,
        # the approval, and the push behind them, so nothing of this
        # workflow's has touched the remote: a pull request standing on the
        # accepted candidate got there because something else -- an agent that
        # pushed its own commit -- put it there. Read as this settlement's own
        # push landing, the record is retired and the issue handed on over a
        # publication nobody proved.
        self._seed_published(head=CANDIDATE_SHA)

        outcome = self._decide(SINGLE_RUN)

        self._assert_unpublished(outcome)

    def test_a_rewind_onto_a_stale_receipt_is_refused(self) -> None:
        # The sharp form of the same move. The receipt is never cleared, so an
        # accepted candidate this issue published in an earlier round is a
        # commit it goes on naming -- and a pull request somebody rewound onto
        # that commit then agrees with every local fact there is. What dates a
        # receipt to THIS settlement is the head it replaced, which has to be
        # the head the verdict was measured over: an earlier attempt's names
        # another, and one written before the pair was recorded names none.
        for lease in (OTHER_SHA, None):
            with self.subTest(lease=lease):
                self.setUp()
                self._seed_published(head=CANDIDATE_SHA)
                self.github.seed_state(self.issue.number, **{
                    **self._pinned(),
                    KEYS.receipt_sha: CANDIDATE_SHA,
                    KEYS.receipt_lease: lease,
                })

                outcome = self._decide(SINGLE_RUN)

                self._assert_unpublished(outcome)

    def test_a_receipt_for_the_candidate_finishes_it(self) -> None:
        # And the same head with a record behind it is the window the
        # carve-out exists for: the receipt says this workflow pushed exactly
        # that commit, so the pull request is standing where this issue put
        # it and what is left to finish is the label and the retirement.
        self._seed_published(head=CANDIDATE_SHA)
        self.github.seed_state(self.issue.number, **{
            **self._pinned(),
            KEYS.receipt_sha: CANDIDATE_SHA,
            KEYS.receipt_lease: PUBLISHED_HEAD_SHA,
        })

        outcome = self._decide(SINGLE_RUN, worktree=WorktreeSeed(push=False))

        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(self._label(), PUBLISHED_SOURCE_STAGE)
