# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a teardown writes down before it deletes, and who finishes it.

The half of the retry that no local artifact carries. A remote branch whose
issue has nothing left on this host is one the scan in ``inventory`` will
never report again, so what leads a later pass back to it is the record the
teardown wrote before it pushed -- and these cases are about that record: that
it is there while the deletion is in flight, that a deletion which failed
leaves it, that a deletion which happened does not, and that a pass with no
candidate and a client of its own finishes what it names.

Real refs and a real bare remote throughout, for the reason the teardown's own
cases are: the record IS a ref in the clone, and a double of the ref store
would prove only that the fixture remembered something.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git import authentication
from orchestrator.git.worktrees import inventory, obligations, reclamation
from orchestrator.git.worktrees.models import (
    ArtifactSurface,
    ProvenTip,
    SurfaceOutcome,
)

from tests.git.worktrees.artifact_test_support import (
    GADGET_SLUG,
    _namespaced_branch,
)
from tests.git.worktrees.candidate_host_test_support import _branch_at
from tests.git.worktrees.eligibility_test_support import ISSUE_NUMBER
from tests.git.worktrees.reclamation_test_support import (
    _holds,
    _ReclaimTestCase,
    _surfaces,
)

CLEANED = SurfaceOutcome.CLEANED
ABSENT = SurfaceOutcome.ABSENT
FAILED = SurfaceOutcome.FAILED

_REMOTE_DELETE_SEAM = "_delete_remote_ref"

_RECORD_SEAM = "_record_obligation"

_READ_SEAM = "_recorded_obligations"


def _settled(
    swept: tuple,
) -> tuple[tuple[ArtifactSurface, str, SurfaceOutcome], ...]:
    """What one pass over the records reports, surface by surface."""
    return tuple(
        (taken.surface, taken.subject, taken.outcome) for taken in swept
    )


class _LedgerDuringDelete:
    """A stand-in for the push that reads the ledger while it is running.

    What it answers is refusal, so the case is about both halves of the
    write-ahead at once: the record is there while the deletion is in flight,
    and it is still there once that deletion has failed.
    """

    def __init__(self, spec) -> None:
        self.spec = spec
        self.recorded = ()

    def __call__(self, *args, **options) -> bool:
        """Read what this host owes at the moment the push would run."""
        self.recorded = obligations._recorded_obligations(self.spec)
        return False


class RecordedRemoteTest(_ReclaimTestCase):
    """What one teardown writes down, and what it lets go of."""

    def test_a_finished_teardown_owes_nothing(self) -> None:
        # The record is a note about a deletion in flight, so a deletion that
        # landed leaves none: a ledger that only grew would have every later
        # pass spending a round trip on branches nobody owes.
        self.published()

        reclaimed = self.spend(self.verdict())

        self.assertTrue(reclaimed.settled)
        self.assertEqual(obligations._recorded_obligations(self.spec), ())
        self.assertEqual(reclamation._reclaim_recorded_remotes(self.spec), ())

    def test_the_record_is_there_before_the_push(self) -> None:
        tip = self.published()
        watched = _LedgerDuringDelete(self.spec)

        with patch.object(authentication, _REMOTE_DELETE_SEAM, watched):
            self.spend(self.verdict())

        self.assertEqual(watched.recorded, (ProvenTip(self.branch, tip),))
        self.assertEqual(
            obligations._recorded_obligations(self.spec),
            (ProvenTip(self.branch, tip),),
        )

    def test_a_record_that_will_not_write_stops_it(self) -> None:
        # A deletion nothing could write down first is one whose failure
        # nothing would carry, so it is not attempted at all.
        self.published()

        with patch.object(
            obligations, _RECORD_SEAM, return_value=False,
        ), patch.object(
            authentication, _REMOTE_DELETE_SEAM,
        ) as pushed:
            reclaimed = self.spend(self.verdict())
            pushed.assert_not_called()

        self.assertEqual(
            self.outcomes(reclaimed), _surfaces(None, FAILED, FAILED),
        )
        self.assertEqual(self.standing()[1:], (True, True))


class ObligationSweepTest(_ReclaimTestCase):
    """The pass that finishes a deletion from the record alone."""

    def owed(self, tip: str) -> ProvenTip:
        """Write down a deletion of this issue's branch at `tip`."""
        obligations._record_obligation(self.spec, self.branch, tip)
        return ProvenTip(self.branch, tip)

    def test_a_failed_delete_is_finished_later(self) -> None:
        # The anchor is taken by somebody else between the reading that named
        # the branch and the deletion it was for, so the teardown has nothing
        # local to keep back -- and the scan a restarted process would run
        # reports no candidate at all. What finishes it is the record.
        self.published()
        cleared = self.verdict()
        _branch_at(self.clone, self.branch)

        with patch.object(
            authentication, _REMOTE_DELETE_SEAM, return_value=False,
        ):
            stopped = self.spend(cleared)

        self.assertEqual(
            self.outcomes(stopped), _surfaces(None, FAILED, ABSENT),
        )
        self.assertFalse(stopped.settled)
        self.assertEqual(
            inventory._local_issue_inventory((self.spec,)).issues, (),
        )

        swept = reclamation._reclaim_recorded_remotes(self.spec)

        self.assertEqual(
            _settled(swept),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, CLEANED),),
        )
        self.assertFalse(self.standing()[2])
        self.assertEqual(obligations._recorded_obligations(self.spec), ())

    def test_a_remote_gone_since_is_let_go(self) -> None:
        # Absent is success here as everywhere: the deletion the record was
        # for has happened, whoever did it, and a record kept over it would
        # be retried forever against an answer that will not change.
        owed = self.owed(self.published())
        self.world.unpublish(self.clone, self.branch)

        swept = reclamation._reclaim_recorded_remotes(self.spec)

        self.assertEqual(
            _settled(swept),
            ((ArtifactSurface.REMOTE_BRANCH, owed.subject, ABSENT),),
        )
        self.assertEqual(obligations._recorded_obligations(self.spec), ())

    def test_a_remote_moved_since_is_let_go(self) -> None:
        # What a record authorizes is a deletion of one commit. The branch
        # carries somebody's work now, so the record is void rather than
        # outstanding -- and the branch is left exactly where it is.
        self.owed(self.published())
        ahead = f"{self.branch}-ahead"
        self.world.commit_on(self.clone, ahead, start=self.branch)
        self.world.publish(self.clone, self.branch, ahead)

        swept = reclamation._reclaim_recorded_remotes(self.spec)

        self.assertEqual(
            tuple(taken.outcome for taken in swept), (FAILED,),
        )
        self.assertEqual(obligations._recorded_obligations(self.spec), ())
        self.assertTrue(self.standing()[2])

    def test_a_record_this_host_does_not_own_stays(self) -> None:
        # The ledger is one clone's, and several repositories may share a
        # clone: a branch another entry publishes has a remote this one knows
        # nothing about, so the record is passed over rather than spent.
        stranger = _namespaced_branch(GADGET_SLUG, ISSUE_NUMBER)
        obligations._record_obligation(
            self.spec, stranger, self.published(stranger),
        )

        swept = reclamation._reclaim_recorded_remotes(self.spec)

        self.assertEqual(swept, ())
        self.assertEqual(
            tuple(
                owed.subject
                for owed in obligations._recorded_obligations(self.spec)
            ),
            (stranger,),
        )
        self.assertTrue(_holds(self.spec, stranger))

    def test_a_ledger_that_will_not_read_is_told(self) -> None:
        # Nothing owed and nobody could say are one answer to a caller that
        # would otherwise report this host as finished.
        with patch.object(obligations, _READ_SEAM, return_value=None):
            swept = reclamation._reclaim_recorded_remotes(self.spec)

        self.assertEqual(
            _settled(swept),
            (
                (
                    ArtifactSurface.REMOTE_BRANCH,
                    obligations.RECLAIM_NAMESPACE,
                    FAILED,
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
