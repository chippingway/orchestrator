# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a teardown writes down before it deletes, and who finishes it.

The half of the retry that no local artifact carries. A remote branch whose
issue has nothing left on this host is one the scan in ``inventory`` will
never report again, so what leads a later pass back to it is the record the
teardown wrote before it pushed -- and these cases are about that record: that
it is there while the deletion is in flight, that a deletion which failed
leaves it, that a deletion which happened does not, that a pass with no
candidate and a client of its own finishes what it names, and that a commit
only the remote has is brought within reach before the record naming it is
judged.

Real refs and a real bare remote throughout, for the reason the teardown's own
cases are: the record IS a ref in the clone, and a double of the ref store
would prove only that the fixture remembered something.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git import authentication
from orchestrator.git.worktrees import (
    evidence,
    inventory,
    obligations,
    paths,
    reclamation,
)
from orchestrator.git.worktrees.models import (
    ArtifactSurface,
    ArtifactVerdict,
    BranchTip,
    ProbeAnswer,
    ProvenTip,
    SurfaceOutcome,
)
from tests.git.worktrees.artifact_test_support import (
    BASE_BRANCH,
    COLLIDING_SLUGS,
    GADGET_SLUG,
    _legacy_branch,
    _namespaced_branch,
    _spec,
)
from tests.git.worktrees.candidate_host_test_support import (
    QUIET,
    _branch_at,
)
from tests.git.worktrees.eligibility_test_support import (
    ISSUE_NUMBER,
    _candidate,
    _github,
    _pull_request,
    _terminal_issue,
)
from tests.git.worktrees.reclamation_test_support import (
    _holds,
    _ReclaimTestCase,
    _surfaces,
    _tip,
)
from tests.workflow.stages.question.question_real_git_test_support import (
    _run_git,
)

CLEANED = SurfaceOutcome.CLEANED
ABSENT = SurfaceOutcome.ABSENT
FAILED = SurfaceOutcome.FAILED

_REMOTE_DELETE_SEAM = "_delete_remote_ref"

_RECORD_SEAM = "_record_obligation"

_READ_SEAM = "_recorded_obligations"

_TARGET_FETCH_SEAM = "_authed_target_fetch"

# The pull request that accounts for a commit no local read can measure, and
# the clone it was pushed from.
PR_NUMBER = 42

PUBLISHER_NAME = "publisher"

# A well-formed object id this clone has never had. `update-ref` refuses to
# write a ref at an object it cannot find, which is the ledger declining one
# note without declining every note.
UNKNOWN_COMMIT = "1111111111111111111111111111111111111111"


def _swept(gh, spec) -> tuple:
    """One pass over the records one repository wrote."""
    return reclamation._reclaim_recorded_notes(gh, spec)


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
        self.assertEqual(_swept(self.gh, self.spec), ())

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

    def test_a_record_made_symbolic_moves_nothing(self) -> None:
        # The ledger lives in the store the per-issue checkouts share, so a
        # record can be pointed at somebody's branch -- and an update-ref that
        # followed it would write this host's note to itself onto that branch,
        # or take it away. Neither half follows one, and the delete refuses
        # outright: what it says it expects is the value this host wrote, and
        # a note standing at somebody else's commit is not it.
        self.published()
        stood_at = _tip(self.clone, BASE_BRANCH)
        elsewhere = self.world.commit_on(self.clone, f"{self.branch}-other")
        record = obligations._obligation_ref(self.spec, self.branch)
        base = f"refs/heads/{BASE_BRANCH}"
        _run_git("symbolic-ref", record, base, cwd=self.clone)

        obligations._record_obligation(self.spec, self.branch, elsewhere)

        self.assertEqual(_tip(self.clone, BASE_BRANCH), stood_at)
        self.assertEqual(
            obligations._recorded_obligations(self.spec),
            (ProvenTip(self.branch, elsewhere),),
        )

        _run_git("symbolic-ref", record, base, cwd=self.clone)

        self.assertFalse(
            obligations._discharge_obligation(
                self.spec, self.branch, elsewhere,
            ),
        )
        self.assertEqual(_tip(self.clone, BASE_BRANCH), stood_at)
        self.assertNotEqual(
            obligations._recorded_obligations(self.spec), (),
        )

    def test_a_branch_back_before_teardown_is_owed(self) -> None:
        # The classification found the branch on neither host, so it cleared
        # no commit for it, and something published it again before the
        # teardown reached the remote. Nothing may be deleted on that showing
        # and nothing local names the issue any more, so what carries it is
        # the reminder -- and the pass that reads that reminder back asks the
        # classification, which by then clears the branch and takes it.
        cleared = self.verdict()
        self.world.publish(self.clone, self.branch, BASE_BRANCH)

        stopped = self.spend(cleared)

        self.assertEqual(
            self.outcomes(stopped), _surfaces(None, FAILED, ABSENT),
        )
        self.assertEqual(
            inventory._local_issue_inventory((self.spec,)).issues, (),
        )
        self.assertEqual(
            tuple(
                owed.subject
                for owed in obligations._recorded_obligations(self.spec)
            ),
            (self.branch,),
        )

        self.assertEqual(
            _settled(_swept(self.gh, self.spec)),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, CLEANED),),
        )
        self.assertFalse(self.standing()[2])
        self.assertEqual(_swept(self.gh, self.spec), ())

    def test_a_remote_nobody_could_read_is_owed(self) -> None:
        # The other way a proofless branch ends the teardown: the remote would
        # not say whether there is anything under that name at all. A reading
        # that established nothing is written down like the other, and it
        # clears itself on the first later pass that finds nothing there.
        cleared = self.verdict()
        unread = BranchTip(answer=ProbeAnswer.UNREADABLE)

        with patch.object(evidence, "_published_tip", return_value=unread):
            stopped = self.spend(cleared)

        self.assertEqual(
            self.outcomes(stopped), _surfaces(None, FAILED, ABSENT),
        )
        self.assertEqual(
            tuple(
                owed.subject
                for owed in obligations._recorded_obligations(self.spec)
            ),
            (self.branch,),
        )

        self.assertEqual(
            _settled(_swept(self.gh, self.spec)),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, ABSENT),),
        )
        self.assertEqual(obligations._recorded_obligations(self.spec), ())

    def test_a_branch_no_record_took_is_reminded(self) -> None:
        # The local copy went before the teardown reached it, so nothing on
        # this host names the issue any more, and the ledger would not take a
        # note at the commit this verdict cleared. What is left to try is the
        # reminder, written at an object every repository knows -- and it is
        # the only thing that has the pass after this one find the branch.
        self.published()
        cleared = ArtifactVerdict(
            _candidate(self.spec, ISSUE_NUMBER, branches=self.branches),
            proven=(ProvenTip(self.branch, UNKNOWN_COMMIT),),
        )
        _branch_at(self.clone, self.branch)

        stopped = self.spend(cleared)

        self.assertEqual(
            self.outcomes(stopped), _surfaces(None, FAILED, ABSENT),
        )
        self.assertEqual(
            inventory._local_issue_inventory((self.spec,)).issues, (),
        )
        self.assertEqual(
            obligations._recorded_obligations(self.spec),
            (ProvenTip(self.branch, obligations._REMINDER_MARK),),
        )

        self.assertEqual(
            _settled(_swept(self.gh, self.spec)),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, CLEANED),),
        )
        self.assertFalse(self.standing()[2])

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

        swept = _swept(self.gh, self.spec)

        self.assertEqual(
            _settled(swept),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, CLEANED),),
        )
        self.assertFalse(self.standing()[2])
        self.assertEqual(obligations._recorded_obligations(self.spec), ())

    def test_a_branch_gone_before_the_verdict_is_owed(self) -> None:
        # The other window: the branch goes between the scan naming it and
        # the classification judging it, so what the verdict clears is the
        # copy the remote carries. The teardown writes that deletion down
        # like any other -- which is the whole difference between a leftover
        # a later pass finds and one nothing on this host can name.
        self.published()
        _branch_at(self.clone, self.branch)

        with patch.object(
            authentication, _REMOTE_DELETE_SEAM, return_value=False,
        ):
            stopped = self.spend(self.verdict())

        self.assertEqual(
            self.outcomes(stopped), _surfaces(None, FAILED, ABSENT),
        )
        self.assertEqual(
            inventory._local_issue_inventory((self.spec,)).issues, (),
        )

        swept = _swept(self.gh, self.spec)

        self.assertEqual(
            _settled(swept),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, CLEANED),),
        )
        self.assertFalse(self.standing()[2])

    def test_a_remote_that_would_not_answer_is_owed(self) -> None:
        # Both halves failing at once, which is the shape nothing else
        # carries: the branch is gone from this clone, so the local surface is
        # rightly a success and the scan has no candidate left to report --
        # and the remote would not say what it holds, so the deletion did not
        # happen. The record went down before that question was even put, so
        # the pass after this one still finds the leftover and finishes it.
        tip = self.published()
        cleared = self.verdict()
        _branch_at(self.clone, self.branch)
        unread = BranchTip(answer=ProbeAnswer.UNREADABLE)

        with patch.object(evidence, "_published_tip", return_value=unread):
            stopped = self.spend(cleared)

        self.assertEqual(
            self.outcomes(stopped), _surfaces(None, FAILED, ABSENT),
        )
        self.assertEqual(
            inventory._local_issue_inventory((self.spec,)).issues, (),
        )
        self.assertEqual(
            obligations._recorded_obligations(self.spec),
            (ProvenTip(self.branch, tip),),
        )
        self.assertEqual(
            _settled(_swept(self.gh, self.spec)),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, CLEANED),),
        )

    def test_a_remote_that_moved_under_it_is_owed(self) -> None:
        # The same shape with the other remote failure: nothing local names
        # the issue any more and the branch on the remote carries work nobody
        # cleared, so this deletes nothing -- and the record it wrote first is
        # what has a later pass report the leftover rather than nothing.
        tip = self.published()
        cleared = self.verdict()
        ahead = f"{self.branch}-ahead"
        self.world.commit_on(self.clone, ahead, start=self.branch)
        _branch_at(self.clone, self.branch)
        self.world.publish(self.clone, self.branch, ahead)

        stopped = self.spend(cleared)

        self.assertEqual(
            self.outcomes(stopped), _surfaces(None, FAILED, ABSENT),
        )
        self.assertEqual(
            inventory._local_issue_inventory((self.spec,)).issues, (),
        )
        self.assertEqual(
            obligations._recorded_obligations(self.spec),
            (ProvenTip(self.branch, tip),),
        )
        self.assertEqual(
            _settled(_swept(self.gh, self.spec)),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, FAILED),),
        )

    def test_a_remote_gone_since_is_let_go(self) -> None:
        # Absent is success here as everywhere: the deletion the record was
        # for has happened, whoever did it, and a record kept over it would
        # be retried forever against an answer that will not change.
        owed = self.owed(self.published())
        self.world.unpublish(self.clone, self.branch)

        swept = _swept(self.gh, self.spec)

        self.assertEqual(
            _settled(swept),
            ((ArtifactSurface.REMOTE_BRANCH, owed.subject, ABSENT),),
        )
        self.assertEqual(obligations._recorded_obligations(self.spec), ())

    def test_a_remote_moved_since_is_kept(self) -> None:
        # The branch carries somebody's work now, so this deletes nothing --
        # and it keeps the record, which is the only thing that would lead
        # anybody back to a branch still standing there. What the record says
        # is which commit this host was cleared to delete, and that stays true
        # however far the remote moves, so the pass after this one -- all a
        # restart has -- reports the leftover again rather than nothing.
        owed = self.owed(self.published())
        ahead = f"{self.branch}-ahead"
        self.world.commit_on(self.clone, ahead, start=self.branch)
        self.world.publish(self.clone, self.branch, ahead)

        swept = _swept(self.gh, self.spec)
        again = _swept(self.gh, self.spec)

        self.assertEqual(
            tuple(taken.outcome for taken in swept + again),
            (FAILED, FAILED),
        )
        self.assertEqual(obligations._recorded_obligations(self.spec), (owed,))
        self.assertTrue(self.standing()[2])


class RecordedPermissionTest(_ReclaimTestCase):
    """A record says which branch to ask about; what may go is asked again."""

    def recreated_elsewhere(self) -> str:
        """Put this branch back on the remote at a commit this clone lacks.

        The reminder, the branch published from a clone of the remote this
        host has nothing to do with, and the terminal pull request that
        accounts for what it is standing on: every piece of the answer except
        the objects, which reach this host only if something fetches them.
        """
        obligations._remind(self.spec, self.branch)
        publisher = self.world.path(PUBLISHER_NAME)
        _run_git(
            "clone", QUIET,
            str(self.world.remote), str(publisher),
            cwd=self.clone,
        )
        recreated = self.world.commit_on(publisher, self.branch)
        self.world.publish(publisher, self.branch, self.branch)
        self.gh.add_pr(_pull_request(PR_NUMBER, self.branch, recreated))
        return recreated

    def test_a_remote_gone_needs_no_permission(self) -> None:
        # Nothing to delete is nothing to clear. The local copy somebody
        # recreated with work of their own would keep every classification
        # refusing, and a record held back on that would be one no later pass
        # could ever settle -- over a branch that is already off the remote.
        obligations._record_obligation(
            self.spec, self.branch, self.published(),
        )
        self.world.unpublish(self.clone, self.branch)
        self.world.commit_on(self.clone, self.branch, start=self.branch)

        swept = _swept(self.gh, self.spec)

        self.assertEqual(
            _settled(swept),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, ABSENT),),
        )
        self.assertEqual(obligations._recorded_obligations(self.spec), ())
        self.assertEqual(_swept(self.gh, self.spec), ())

    def test_a_remote_that_advanced_is_reclaimed(self) -> None:
        # The record names what was cleared when it was written, and the
        # branch has moved on since. The pass that finds the new work
        # unaccounted for keeps the record; the one after it, once that work
        # has landed, spends it on what the branch is standing on now.
        tip = self.published()
        obligations._record_obligation(self.spec, self.branch, tip)
        self.world.commit_on(self.clone, self.branch, start=self.branch)
        self.world.publish(self.clone, self.branch, self.branch)

        held = _swept(self.gh, self.spec)

        self.assertEqual(tuple(taken.outcome for taken in held), (FAILED,))
        self.assertEqual(
            obligations._recorded_obligations(self.spec),
            (ProvenTip(self.branch, tip),),
        )

        self.world.publish(self.clone, BASE_BRANCH, self.branch)

        self.assertEqual(
            _settled(_swept(self.gh, self.spec)),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, CLEANED),),
        )
        self.assertFalse(self.standing()[2])
        self.assertEqual(obligations._recorded_obligations(self.spec), ())

    def test_a_record_for_a_live_issue_is_refused(self) -> None:
        # The ledger is a ref store the agents this orchestrator runs can
        # write, so one of them can put a correctly named record at the very
        # commit the branch is on. What stops it is that a record is not a
        # proof: the classification is asked again, and this issue has not
        # ended.
        obligations._record_obligation(
            self.spec, self.branch, self.published(),
        )
        self.gh = _github(_terminal_issue(closed=False))

        swept = _swept(self.gh, self.spec)

        self.assertEqual(
            tuple(taken.outcome for taken in swept), (FAILED,),
        )
        self.assertTrue(self.standing()[2])
        self.assertNotEqual(
            obligations._recorded_obligations(self.spec), (),
        )

    def test_a_remote_only_commit_is_reclaimed(self) -> None:
        # Ancestry is a question about objects this clone holds, so a commit
        # that has only ever existed on the remote leaves the base read
        # unable to answer -- and an unanswerable read stops the
        # classification before the pull request that accounts for the commit
        # is ever reached. A record kept on that showing is one no repetition
        # settles, so the commit is brought within reach first.
        recreated = self.recreated_elsewhere()

        self.assertIs(
            evidence._carries_commit(self.spec, recreated),
            ProbeAnswer.REFUTED,
        )
        self.assertEqual(
            _settled(_swept(self.gh, self.spec)),
            ((ArtifactSurface.REMOTE_BRANCH, self.branch, CLEANED),),
        )
        self.assertFalse(self.standing()[2])
        self.assertEqual(obligations._recorded_obligations(self.spec), ())

    def test_a_commit_nothing_fetched_is_kept(self) -> None:
        # The fail-closed half: a fetch that did not run leaves the proof
        # exactly where it was without one, so nothing is deleted -- and the
        # record is still there, which is what has the pass after this one
        # find the leftover rather than nothing.
        self.recreated_elsewhere()
        refused = authentication._failed_fetch("nothing came back")

        with patch.object(
            authentication, _TARGET_FETCH_SEAM, return_value=refused,
        ) as asked:
            swept = _swept(self.gh, self.spec)
            asked.assert_called_once_with(self.spec, self.branch)

        self.assertEqual(tuple(taken.outcome for taken in swept), (FAILED,))
        self.assertTrue(self.standing()[2])
        self.assertNotEqual(
            obligations._recorded_obligations(self.spec), (),
        )

    def test_a_record_of_unproven_work_is_refused(self) -> None:
        # The same store, and a record naming exactly what the branch is
        # standing on -- which is all a forger needs when a record is taken as
        # proof. The commit is on no base and in no pull request, so the
        # classification keeps it and the deletion never runs.
        tip = self.world.commit_on(self.clone, self.branch)
        self.world.publish(self.clone, self.branch, self.branch)
        obligations._record_obligation(self.spec, self.branch, tip)

        swept = _swept(self.gh, self.spec)

        self.assertEqual(
            tuple(taken.outcome for taken in swept), (FAILED,),
        )
        self.assertTrue(self.standing()[2])


class LedgerOwnershipTest(_ReclaimTestCase):
    """Which records a repository may read, and which it may take away."""

    def test_a_record_rewritten_since_is_not_taken(self) -> None:
        # The ledger is a store the per-issue checkouts share, so a record can
        # be written again between the pass that read it and the deletion that
        # would take it away -- by a pass owed a commit of its own, or by a
        # reminder saying the branch has to be asked about again. The delete
        # states what it read, so the note that arrived after it stays; stated
        # correctly, the same delete takes it.
        tip = self.published()
        obligations._record_obligation(self.spec, self.branch, tip)
        rewritten = self.world.commit_on(self.clone, f"{self.branch}-again")
        obligations._record_obligation(self.spec, self.branch, rewritten)

        self.assertFalse(
            obligations._discharge_obligation(self.spec, self.branch, tip),
        )
        self.assertEqual(
            obligations._recorded_obligations(self.spec),
            (ProvenTip(self.branch, rewritten),),
        )

        self.assertTrue(
            obligations._discharge_obligation(
                self.spec, self.branch, rewritten,
            ),
        )
        self.assertEqual(obligations._recorded_obligations(self.spec), ())

    def test_a_record_of_a_clone_mate_is_not_read(self) -> None:
        # Two repositories on one clone derive the same legacy branch name,
        # which is why the attribution behind the scan refuses to charge that
        # name to either of them. Their records are told apart by the
        # repository they were written under instead, so the deletion this one
        # runs goes to the remote that actually carries the branch -- and the
        # entry beside it never sees the record at all.
        legacy = _legacy_branch(ISSUE_NUMBER)
        obligations._record_obligation(
            self.spec, legacy, self.published(legacy),
        )
        clone_mate = _spec(GADGET_SLUG, self.clone)

        self.assertEqual(
            _swept(self.gh, clone_mate), (),
        )
        self.assertEqual(
            _settled(_swept(self.gh, self.spec)),
            ((ArtifactSurface.REMOTE_BRANCH, legacy, CLEANED),),
        )

    def test_a_record_of_a_colliding_slug_is_not_read(self) -> None:
        # The two slugs the ref-safe sanitizer cannot tell apart, which is
        # the pair the attribution behind the scan refuses to attribute
        # anything to. Their branches are one name, so a ledger keyed the way
        # the branch namespace is would be one room -- and either entry would
        # read the other's note, classify it against its own GitHub, and
        # delete on its own remote. The digest of the untransformed slug is
        # what keeps the two apart.
        one, other = (_spec(slug, self.clone) for slug in COLLIDING_SLUGS)
        owed = paths._branch_name(one, ISSUE_NUMBER)
        obligations._record_obligation(one, owed, self.published(owed))

        self.assertNotEqual(
            obligations._records_prefix(one),
            obligations._records_prefix(other),
        )
        self.assertEqual(obligations._recorded_obligations(other), ())
        self.assertEqual(_swept(self.gh, other), ())
        self.assertEqual(
            tuple(
                record.subject
                for record in obligations._recorded_obligations(one)
            ),
            (owed,),
        )

    def test_a_record_this_host_does_not_own_stays(self) -> None:
        # The ledger is one clone's, and several repositories may share a
        # clone: a branch another entry publishes has a remote this one knows
        # nothing about, so the record is passed over rather than spent.
        stranger = _namespaced_branch(GADGET_SLUG, ISSUE_NUMBER)
        obligations._record_obligation(
            self.spec, stranger, self.published(stranger),
        )

        swept = _swept(self.gh, self.spec)

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
            swept = _swept(self.gh, self.spec)

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
