# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which pull request an accepted candidate is handed on against.

`pr_number` is whatever the issue recorded when it entered the gate, and by
the time a `single` is settled it can be none of the things the handoff needs
it to be: a plan pull request a human merged, or one a publication that
crashed already put the measured commit on. So the COMMIT is what the pull
request is found by, in any state -- the search by branch and open state the
ordinary publication makes cannot see either of those.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.workflow.late_split.models import LateFailure
from orchestrator.workflow.stages.decomposition.late_models import (
    _LateDisposition,
)

from tests.support.fakes import FakePR
from tests.workflow.fixtures import LABEL_DECOMPOSING, LABEL_IMPLEMENTING
from tests.workflow.stages.decomposition.late_settlement_support import (
    CANDIDATE_BRANCH,
    CARRYING_PR_NUMBER,
    ERROR,
    GuardedLateCase,
    KEY_BRANCH,
    KEY_PR_NUMBER,
    SETTLED_PR_NUMBER,
)
from tests.workflow.stages.decomposition.late_settlement_support import (
    PARK_PR_UNRECONCILED,
    SINGLE_RUN,
    WORKFLOW_LOG,
)
from tests.workflow.stages.decomposition.late_test_support import (
    CANDIDATE_SHA,
    EVENT_LATE_FAILURE,
    KEYS,
    OTHER_SHA,
    generation_state,
    late_generation,
)

GET_PR = "get_pr"

PR_CLOSED = "closed"

PR_OPEN = "open"


class _SecondReadFails:
    """A pull-request read that answers once and then dies.

    The hold reconciliation reads the recorded pull request at the top of the
    tick and the settlement reads it again at the bottom. Only the second one
    is the read under test, so the first is allowed through.
    """

    def __init__(self, github) -> None:
        self._get_pr = github.get_pr
        self._answered = False

    def __call__(self, pr_number):
        if self._answered:
            raise RuntimeError("could not read it this time")
        self._answered = True
        return self._get_pr(pr_number)


class _PrStateCase(GuardedLateCase):
    """One late issue whose branch and recorded pull request are seeded."""

    def setUp(self) -> None:
        super().setUp()
        self._seed_recording(None)

    def _seed_recording(self, pr_number) -> None:
        """Re-seed this issue with its branch and what it records as its PR."""
        recorded = {KEY_BRANCH: CANDIDATE_BRANCH}
        if pr_number is not None:
            recorded[KEY_PR_NUMBER] = pr_number
        self.github.seed_state(
            self.issue.number,
            **generation_state(late_generation()),
            **recorded,
        )

    def _add_pr(self, number: int, *, merged: bool, carries: str) -> None:
        """One pull request on the candidate's branch, in the state named."""
        self.github.add_pr(FakePR(
            number=number,
            head_branch=CANDIDATE_BRANCH,
            state=PR_CLOSED if merged else PR_OPEN,
            merged=merged,
            commit_shas=(carries,),
        ))


class ExactCommitReconciliationTest(_PrStateCase, unittest.TestCase):
    """The handoff names the pull request the measured commit is on."""

    def test_a_pr_already_carrying_it_is_recorded(self) -> None:
        # A publication that pushed and died before recording its number
        # leaves the commit on a pull request nothing points at. Searched by
        # open state alone it is invisible, and the candidate is published a
        # second time.
        self._add_pr(CARRYING_PR_NUMBER, merged=True, carries=CANDIDATE_SHA)

        outcome = self._decide(SINGLE_RUN)

        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(self._pinned().get(KEY_PR_NUMBER), CARRYING_PR_NUMBER)

    def test_a_settled_recorded_pr_is_dropped(self) -> None:
        # Carried into the implementing stage, a merged pull request that is
        # not the plan ends the issue as done -- on a change the adjudicated
        # candidate is not in.
        self._seed_recording(SETTLED_PR_NUMBER)
        self._add_pr(SETTLED_PR_NUMBER, merged=True, carries=OTHER_SHA)

        outcome = self._decide(SINGLE_RUN)

        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertIsNone(self._pinned().get(KEY_PR_NUMBER))
        self.assertEqual(
            self.github.workflow_label(self.issue), LABEL_IMPLEMENTING,
        )

    def test_an_open_recorded_pr_is_kept(self) -> None:
        # Nothing carries the commit yet, and an open pull request on the
        # branch is exactly what the ordinary publication reuses.
        self._seed_recording(SETTLED_PR_NUMBER)
        self._add_pr(SETTLED_PR_NUMBER, merged=False, carries=OTHER_SHA)

        outcome = self._decide(SINGLE_RUN)

        self.assertEqual(outcome.disposition, _LateDisposition.SETTLED)
        self.assertEqual(self._pinned().get(KEY_PR_NUMBER), SETTLED_PR_NUMBER)


class UnreconciledPrTest(_PrStateCase, unittest.TestCase):
    """A pull request nobody could confirm publishes nothing.

    "Nobody could say" is not "no pull request carries it", and only the
    second one may publish: the first would open a duplicate for a commit
    already on one, or hand a merged pointer to a terminal that ends the issue
    on it.
    """

    def test_an_unreadable_lookup_publishes_nothing(self) -> None:
        self.github.unreadable_pr_lookups.add(CANDIDATE_BRANCH)

        outcome = self._decide(SINGLE_RUN)

        self._assert_unreconciled(outcome)

    def test_an_unreadable_record_publishes_nothing(self) -> None:
        self._seed_recording(SETTLED_PR_NUMBER)
        self._add_pr(SETTLED_PR_NUMBER, merged=True, carries=OTHER_SHA)
        refused = patch.object(
            self.github, GET_PR, _SecondReadFails(self.github),
        )

        with refused:
            with self.assertLogs(WORKFLOW_LOG, level=ERROR):
                outcome = self._decide(SINGLE_RUN)

        self._assert_unreconciled(outcome)

    def _assert_unreconciled(self, outcome) -> None:
        """Parked, with nothing exempted and nothing handed on."""
        self.assertEqual(outcome.disposition, _LateDisposition.PARKED)
        pinned = self._pinned()
        self.assertEqual(pinned.get(KEYS.park_reason), PARK_PR_UNRECONCILED)
        self.assertNotIn(KEYS.exempt_sha, pinned)
        self.assertEqual(
            self.github.workflow_label(self.issue), LABEL_DECOMPOSING,
        )
        self.assertEqual(
            self._events_named(EVENT_LATE_FAILURE)[-1].get("failure"),
            LateFailure.PR_RECONCILE_FAILED,
        )


if __name__ == "__main__":
    unittest.main()
