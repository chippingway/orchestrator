# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The reading a cancelled cycle's terminal may be written on.

`rejected` takes the owner off both labels the closed-owner sweep queries, so
an issue that reaches it is one nothing revisits. Everything the ending settles
is therefore settled first -- but the held plan pull request is settled at the
TOP of the pass, and what stands between that ask and this write is a branch
delete, a ref delete, and a fresh read of every recorded consumer.

A human reopening the change inside them leaves the record saying `reconciled`
and the remote saying open, and a terminal taken on the record would leave that
pull request standing under a cancelled cycle with nothing coming back for it.
So the pull request is asked again immediately before the terminal, and what
these cases pin is that reading.
"""
from __future__ import annotations

import unittest

from tests.workflow.stages.decomposition.late_cancel_support import (
    ClosedOwnerCase,
)
from tests.workflow.stages.decomposition.late_cleanup_support import (
    LABEL_REJECTED,
    PARENT_NUMBER,
    RecordedDelete,
    SNAPSHOT_REF,
    STATE_FAILED,
    SnapshotOutcome,
)
from tests.workflow.stages.decomposition.late_test_support import (
    PLAN_PR_NUMBER,
)

_DELETED = SnapshotOutcome.DELETED

_WORKFLOW_LOG = "orchestrator.workflow"

_EVENT_FAILURE = "late_failure"

_PR_RECONCILE_FAILED = "pr_reconcile_failed"

_PLAN_PR_TARGET = str(PLAN_PR_NUMBER)

_PR_OPEN = "open"

_PR_CLOSED = "closed"

_RETIRED = ((PARENT_NUMBER, LABEL_REJECTED),)


class _ReopeningDelete(RecordedDelete):
    """A human reopening the held plan PR inside the snapshot delete.

    The one window the record cannot describe: the pull request was settled
    at the top of the pass and the entry has read `reconciled` ever since,
    while the remote work between that ask and the terminal is long enough
    for somebody to reopen the change inside it.

    `refusing` is the same reopen with the reclose declined, which is what
    makes the terminal wait rather than being written over an obligation this
    visit could not settle.
    """

    def __init__(
        self, outcome, github, *, refusing: bool = False, **answers,
    ) -> None:
        super().__init__(outcome, **answers)
        self._github = github
        self._refusing = refusing

    def __call__(self, *call_args, **call_options):
        self._github.pulls[PLAN_PR_NUMBER].state = _PR_OPEN
        if self._refusing:
            self._github._pull_state._unsupersedable_prs.add(PLAN_PR_NUMBER)
        return super().__call__(*call_args, **call_options)


class ReopenedPlanPrTest(ClosedOwnerCase, unittest.TestCase):
    """A change reopened while the ending was reclaiming somebody's remote."""

    def test_a_pr_reopened_mid_pass_is_reclosed(self) -> None:
        seeded = self._closed_owner()
        self._holding_plan_pr(seeded)
        reopening = _ReopeningDelete(_DELETED, seeded.github)

        with self.assertLogs(_WORKFLOW_LOG):
            seeded.swept_by(self, reopening)

        self.assertEqual(reopening.refs, [SNAPSHOT_REF])
        self.assertEqual(
            seeded.github.pulls[PLAN_PR_NUMBER].state, _PR_CLOSED,
        )
        self.assertEqual(len(seeded.github.posted_pr_comments), 1)
        self.assertEqual(tuple(self._labels(seeded)), _RETIRED)

    def test_a_reclose_that_fails_holds_the_end(self) -> None:
        # The other side of the same reading: a pull request that is open
        # again and will not close is an obligation this visit cannot settle,
        # so the entry the earlier ask left `reconciled` goes back to `failed`
        # and the terminal waits for the sweep that follows rather than being
        # written over it.
        seeded = self._closed_owner()
        self._holding_plan_pr(seeded)

        with self.assertLogs(_WORKFLOW_LOG):
            seeded.swept_by(self, _ReopeningDelete(
                _DELETED, seeded.github, refusing=True,
            ))

        self.assertEqual(self._states(seeded)[_PLAN_PR_TARGET], STATE_FAILED)
        self.assertEqual(
            [
                record["failure"]
                for record in self._events_named(seeded, _EVENT_FAILURE)
            ],
            [_PR_RECONCILE_FAILED],
        )
        self.assertEqual(self._labels(seeded), [])


if __name__ == "__main__":
    unittest.main()
