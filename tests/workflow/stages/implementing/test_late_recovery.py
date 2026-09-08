# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Where a parked issue's committed work goes when the park is answered.

Every park the size gate takes is answered ahead of the spawn, because on all
three the work in question is committed already: the road below would buy a
second developer run for an implementation the first one finished. What each
hands its answer to is the same publication seam that work came out of, so a
recovery reaches exactly the outcomes a fresh disposition does and decides
nothing the gate would have decided.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from orchestrator.git.measurement.models import FrozenCommit
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.verification.probes import _WorktreeStatus
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.stages.implementing import (
    disposition as _disposition,
    late_command as _command,
    late_consent as _consent,
    late_recovery as _recovery,
    state as _state,
)
from tests.workflow.stages.implementing import (
    late_consent_test_support as support,
)

_PUBLISH_COMMITTED_WORK = "_publish_committed_work"
_WORKTREE_PATH = "_worktree_path"
_WORKTREE_STATUS = "_worktree_status"

# A checkout the recovery's existence probe never finds, which is the one
# outcome the publication seam cannot reach on its own: there is no commit to
# read there and a fresh run would answer with different work.
_MISSING_WORKTREE = Path("/tmp/orchestrator-test-late-recovery-gone")

# The three readings a checkout can give the question this road asks it: a
# tree proved to be carrying nothing loose, one carrying work no push would
# publish, and one nothing could read -- which is not a clean tree either.
_CLEAN_TREE = _WorktreeStatus(readable=True)
_DIRTY_TREE = _WorktreeStatus(readable=True, paths=("src/left_behind.py",))
_UNREADABLE_TREE = _WorktreeStatus(readable=False)

# A commit the checkout is standing on that the park's own record does not
# name: work that replaced what an operator decided about.
_MOVED_HEAD_SHA = "e" * support.SHA_LENGTH

# A reading the ceiling lets through, so the seam's answer to a head nobody
# authorized is a push rather than a park.
_SMALL_ADDITIONS = 12

# The sentence a command naming another commit earns, receipt and all, as the
# tick that died before recording it left it on the thread.
_REFUSAL = "that names another commit\n\n{marker}"

# A human taking their authorization back, under a marker of ours they quoted
# off the comment they are answering. Both markers are plain text in a public
# thread, and the token this orchestrator posts under belongs to a person, so
# a reviewer's retraction arrives carrying our marker AND our login.
_RETRACTION = "actually, hold off -- re: {quoted}"

_ORCHESTRATOR_IDS = "orchestrator_comment_ids"
_WRITE_PINNED_STATE = "write_pinned_state"


@dataclass
class _Routed:
    """Where one parked tick's committed work went, and whether it went.

    The publication seam this recovery owes its answer to, beside whether the
    tick was this owner's at all -- the two facts a case is about, since every
    other effect a road has is on the record and read from there.
    """

    published: object
    routed: bool = False


class UnauthorizedExemptionRecoveryTest(
    support._ParkedCase, unittest.TestCase,
):
    """The command that ends the authorization park, routed and no more.

    The command is recognized here and ACTED on where the reading is, because
    that is where the terms of an authorization come from -- so what this owes
    is the routing, and the gate answer decides everything else.
    """

    def test_the_command_republishes_the_work(self) -> None:
        # Back through the same publication seam it came out of, so the answer
        # reaches the outcomes a fresh disposition does -- and never the spawn
        # below, which would pay for a developer over committed work.
        self._reply(support.AUTHORIZE)

        routed = self._recovers()

        self.assertTrue(routed.routed)
        routed.published.assert_called_once()

    def test_a_command_it_cannot_act_on_still_routes(self) -> None:
        # The sentence a command naming another commit earns is the gate's to
        # say, since only the owner holding a reading knows which candidate is
        # waiting. Left unrouted, the reply would fall to the ordinary resume
        # and spawn a developer over work that is already committed.
        self._reply(support.AUTHORIZE_ANOTHER)

        routed = self._recovers()

        self.assertTrue(routed.routed)
        routed.published.assert_called_once()

    def test_guidance_is_left_for_the_resume(self) -> None:
        # A reply whose last word is not the command belongs to the road that
        # feeds it to the developer.
        self._reply(support.GUIDANCE)

        routed = self._recovers()

        self.assertFalse(routed.routed)
        routed.published.assert_not_called()

    def test_a_thread_with_no_command_routes_nothing(self) -> None:
        routed = self._recovers()

        self.assertFalse(routed.routed)
        routed.published.assert_not_called()

    def test_the_park_flags_are_left_standing(self) -> None:
        # The write that records the authorization is the write that takes
        # them off, so a tick that could not fingerprint the pair leaves the
        # issue exactly as parked as it found it rather than durably unparking
        # an issue nothing published.
        self._reply(support.AUTHORIZE)

        self._recovers()

        pinned = self._pinned()
        self.assertTrue(pinned[_state._AWAITING_HUMAN])
        self.assertEqual(
            pinned[_state._PARK_REASON],
            support._command.PARK_UNAUTHORIZED_EXEMPTION,
        )

    def _recovers(
        self,
        worktree: Path = support.TEMP_WORKTREE_ROOT,
        tree: _WorktreeStatus = _CLEAN_TREE,
    ):
        """Route one parked tick, saying what it routed and where.

        The publication seam is patched and nothing else is, so a case reads
        the routing off one call and everything a road did to the record off
        the record itself. The tree reading is the caller's, since what this
        road asks the checkout is the question the seam would have asked.
        """
        seams = _Routed(
            published=patch.object(_disposition, _PUBLISH_COMMITTED_WORK),
        )
        with (
            patch.object(
                _worktree_paths, _WORKTREE_PATH, return_value=worktree,
            ),
            patch.object(
                _verification_probes, _WORKTREE_STATUS, return_value=tree,
            ),
            seams.published as published,
        ):
            seams.routed = _recovery._recovers_a_late_park(
                self.github, support._TEST_SPEC, self.issue, self._state(),
            )
            seams.published = published
        return seams


class UnpublishableCheckoutHoldTest(support._ParkedCase, unittest.TestCase):
    """Every road that answers the command and reaches no publication.

    A checkout the seam would refuse is not a decision anybody made, so
    nothing about it may spend the decision already on the thread. Held
    silently, the park, the command and the record are all still there for the
    poll that finds the worktree back.
    """

    def test_an_unpublishable_tree_writes_nothing(self) -> None:
        # The seam below reads the tree before a verdict can be recorded, and
        # its refusal parks under a reason of its own. Reached on this road,
        # that reason takes the authorization park's off and its notice moves
        # the watermark past the command still standing -- so the operator is
        # asked to authorize the same commit again once they clean the tree.
        # A tree nothing could READ is refused beside a dirty one, since a
        # reading that established nothing is not evidence of a clean tree.
        for described, tree in (
            ("carrying uncommitted work", _DIRTY_TREE),
            ("unreadable", _UNREADABLE_TREE),
        ):
            with self.subTest(tree=described):
                self.setUp()
                self._reply(support.AUTHORIZE)
                before = dict(self._pinned())

                routed = self._recovers(tree=tree)

                self.assertTrue(routed.routed)
                routed.published.assert_not_called()
                self.assertEqual(self._pinned(), before)
                self.assertEqual(self.github.posted_comments, [])

    def test_a_cleaned_tree_needs_no_command(self) -> None:
        # The other half, and the whole of what holding quietly buys: the
        # command is still the last fresh word on the thread, so the poll
        # after an operator cleans the checkout publishes on it.
        self._reply(support.AUTHORIZE)
        self._recovers(tree=_DIRTY_TREE)

        routed = self._recovers()

        self.assertTrue(routed.routed)
        routed.published.assert_called_once()

    def test_a_missing_checkout_writes_nothing(self) -> None:
        # There is no commit to read there, the recorded SHA is evidence no
        # fresh checkout may stand in for, and re-running the developer would
        # answer with different work -- so it owns the tick and publishes
        # nothing. What it may not do is re-park under a reason of its own:
        # the notice that would go with one moves the watermark past the
        # command still standing, and its reason takes this park's off, so an
        # operator who put the worktree back would be asked for the same
        # decision again on an issue now waiting for a different reply.
        self._reply(support.AUTHORIZE)
        before = dict(self._pinned())

        routed = self._recovers(worktree=_MISSING_WORKTREE)

        self.assertTrue(routed.routed)
        routed.published.assert_not_called()
        self.assertEqual(self._pinned(), before)
        self.assertEqual(self.github.posted_comments, [])

    def test_a_restored_checkout_needs_no_command(self) -> None:
        # The whole of what holding quietly buys: the command the operator
        # already wrote is still the last fresh word on the thread, so the
        # poll after the worktree comes back publishes on it.
        self._reply(support.AUTHORIZE)
        self._recovers(worktree=_MISSING_WORKTREE)

        routed = self._recovers()

        self.assertTrue(routed.routed)
        routed.published.assert_called_once()

    _recovers = UnauthorizedExemptionRecoveryTest._recovers


class SeamHeldParkTest(support._ParkedCase, unittest.TestCase):
    """The park survives whatever the real publication seam does with it.

    Driven through a whole tick rather than against a mocked seam, because
    every one of these is the seam itself refusing: a tree it reads for a
    second time, a head it proves for itself, a sentence an earlier tick
    posted and never recorded. A double in its place answers none of them.
    """

    def test_a_second_read_keeps_the_park(self) -> None:
        # The tree is read once before the seam is entered and again inside
        # it, and everything between is time something can write in. The
        # seam's own refusal parks under a reason of its own and its notice
        # moves the watermark past the command -- so the park is put back
        # rather than merely guarded, and the operator who cleans the tree is
        # not asked to authorize the same commit twice.
        self._seed(**support.measured_pair())
        self._reply(support.AUTHORIZE)

        mocks = self._run_tick(tree_states=(_CLEAN_TREE, _DIRTY_TREE))

        self._assert_still_parked(mocks)

    def test_a_moved_head_keeps_the_park(self) -> None:
        # A clean checkout standing somewhere else passes every question about
        # the tree and is still not the commit anybody authorized: the record
        # froze one pair and the notice named it. Read small, the seam would
        # PUSH whatever it found there -- which is the one refusal the park
        # being put back afterwards cannot undo, since the work is on the
        # remote by then.
        self._seed(**support.measured_pair())
        self._reply(support.AUTHORIZE)

        mocks = self._run_tick(
            candidate_commit=FrozenCommit(sha=_MOVED_HEAD_SHA),
            added_lines=_SMALL_ADDITIONS,
        )

        self._assert_still_parked(mocks)

    def _assert_still_parked(self, mocks) -> None:
        """Nobody was resumed, nothing was published, and the park stands."""
        mocks[support.RUN_AGENT].assert_not_called()
        mocks[support.PUSH_BRANCH].assert_not_called()
        pinned = self._pinned()
        self.assertTrue(pinned[_state._AWAITING_HUMAN])
        self.assertEqual(
            pinned[_state._PARK_REASON],
            support._command.PARK_UNAUTHORIZED_EXEMPTION,
        )
        self.assertEqual(self.github.label_history, [])


class LostWriteAttributionTest(support._ParkedCase, unittest.TestCase):
    """Comments of ours the write that would have recorded them never reached.

    Two of this stage's writes post before they persist the id saying the post
    was ours. What a later reader cannot attribute it treats as somebody's
    word, so our own prose becomes the last reply, the reading hands the tick
    back, and the resume spawns a developer against it.
    """

    def test_a_stranded_receipt_resumes_nobody(self) -> None:
        # The sentence a refused command earns is posted before the write that
        # records posting it, so a tick dying between the two leaves it on the
        # thread with nothing saying it is ours. Read as somebody's word it is
        # the last reply and not the command, so the tick is handed back and
        # the ordinary resume spawns a developer against our own refusal.
        self._seed(**support.measured_pair())
        answered = self._reply(support.AUTHORIZE_ANOTHER)
        said = self._strand_a_refusal(answered)

        mocks = self._run_tick()

        self._assert_still_parked(mocks)
        self.assertIn(said, self._pinned()[_ORCHESTRATOR_IDS])
        self.assertEqual(
            self._pinned()[_state._LAST_ACTION_COMMENT_ID],
            support.PRIOR_ACTION_COMMENT_ID,
        )

    def test_a_corrected_command_survives_the_repair(self) -> None:
        # What repairing the LEDGER buys over moving the watermark. An
        # operator who read the refusal and got the command right before this
        # tick ran wrote it UNDER our sentence, so a watermark moved to that
        # sentence would consume their answer unread and the park would stand
        # over a decision nobody would ever see again.
        self._seed(**support.measured_pair())
        answered = self._reply(support.AUTHORIZE_ANOTHER)
        corrected = self._reply(support.AUTHORIZE)
        self._strand_a_refusal(answered)

        self._run_tick()

        self.assertEqual(
            _command._read_the_park(
                self.github, self.issue, self._state(),
            ).comment_id,
            corrected,
        )

    def test_a_crashed_seam_notice_resumes_nobody(self) -> None:
        # The seam's notice is the one sentence on this park nothing here
        # worded, so there is no receipt to stamp on it and no reading of the
        # thread could ever pick it out. It is recorded as it LANDS instead,
        # by the process that posted it -- so a tick dying past that point
        # comes back to the park intact and the notice attributed, rather than
        # to prose of ours standing over the command and a resume against it.
        self._seed(**support.measured_pair())
        self._reply(support.AUTHORIZE)
        self._crash_past_the_seam()

        mocks = self._run_tick()

        mocks[support.RUN_AGENT].assert_not_called()
        self.assertIn(
            self.github.latest_comment_id(self.issue),
            self._pinned()[_ORCHESTRATOR_IDS],
        )
        self.assertIsNotNone(
            _command._read_the_park(self.github, self.issue, self._state()),
        )

    def _crash_past_the_seam(self) -> None:
        """Run the tick whose second read is dirty, dying before it restores.

        The write that puts the park back is the one that records what the
        seam posted, so killing it is exactly the window: the notice is on the
        thread and nothing on the comment says it is ours.
        """
        with (
            patch.object(
                self.github, _WRITE_PINNED_STATE,
                side_effect=support.DiesPastTheFirstWrite(self.github),
            ),
            self.assertRaises(support.CrashedTick),
        ):
            self._run_tick(tree_states=(_CLEAN_TREE, _DIRTY_TREE))

    def _strand_a_refusal(self, answered: int) -> int:
        """Post the refusal a lost write never recorded, and say which it is.

        In the two steps the road itself makes them: the receipt this sentence
        is about to be stamped with is recorded durably first, and then the
        sentence goes out through the owner that posts every one of them and
        the state carrying its id is thrown away, which is the write that was
        lost.
        """
        marked = self._state()
        marked.set(_state._HELD_RECEIPT, self._refusal_receipt(answered))
        self.github.write_pinned_state(self.issue, marked)
        posted = _comments._post_issue_comment(
            self.github, self.issue, self._state(),
            _REFUSAL.format(marker=self._refusal_receipt(answered)),
        )
        return posted.id

    def _refusal_receipt(self, answered) -> str:
        """The receipt a refusal answering this reply is stamped with."""
        return _consent._RECEIPTS["refused"].format(
            issue=support.ISSUE_NUMBER, scope=answered,
        )

    _assert_still_parked = SeamHeldParkTest._assert_still_parked


class QuotedMarkerAttributionTest(support._ParkedCase, unittest.TestCase):
    """What a receipt may never claim, and what it takes to claim anything.

    Both of this stage's markers are plain text in a public thread, and the
    token it posts under belongs to a person -- so a reviewer's retraction
    arrives carrying our marker AND our login. Claimed as ours it is dropped
    from the reading, and on a park read by its last fresh reply that leaves
    the authorization underneath it the last word.
    """

    def test_a_quoted_receipt_owed_none_claims_none(self) -> None:
        # The reviewer answering a refusal quotes the receipt it is stamped
        # with, from the very token this orchestrator posts under. With no
        # sentence outstanding there is nothing to attribute at all, so a rule
        # reading that receipt wherever it stands would claim their retraction,
        # drop it on the next tick's reading, and publish on the authorization
        # beneath it.
        self._seed(**support.measured_pair())
        authorized = self._reply(support.AUTHORIZE)
        retracted = self._retracts(self._refusal_receipt(authorized))

        first, second = self._run_tick(), self._run_tick()

        self.assertNotIn(retracted, self._attributed())
        self._assert_published_nothing(first, second)

    def test_a_receipt_over_no_sentence_claims_none(self) -> None:
        # The window a tick that died BEFORE its post leaves: a receipt is
        # recorded and nothing of ours ever reached the thread. Anything that
        # licensed a claim on the window alone would take the next reply to
        # arrive -- and under a shared token that reply carries our marker and
        # our login, so it would be claimed, dropped, and the older
        # authorization would publish on consent already withdrawn.
        self._seed(**{
            _state._HELD_RECEIPT: self._refusal_receipt(support.STRANGER_SHA),
            **support.measured_pair(),
        })
        self._reply(support.AUTHORIZE)
        retracted = self._retracts(_comments._ORCH_COMMENT_MARKER)

        first, second = self._run_tick(), self._run_tick()

        self.assertNotIn(retracted, self._attributed())
        self._assert_published_nothing(first, second)

    def test_a_retraction_past_our_own_survives(self) -> None:
        # The same reply where a sentence of ours really is stranded. Ours is
        # the earlier carrier of that receipt -- a quote can only follow what
        # it quotes -- and it is the whole of what may be claimed. Taking
        # theirs as well would leave the authorization under it the last word.
        self._seed(**support.measured_pair())
        answered = self._reply(support.AUTHORIZE_ANOTHER)
        said = self._strand_a_refusal(answered)
        retracted = self._retracts(self._refusal_receipt(answered))

        first, second = self._run_tick(), self._run_tick()

        self.assertIn(said, self._attributed())
        self.assertNotIn(retracted, self._attributed())
        self._assert_published_nothing(first, second)

    def _assert_published_nothing(self, *ticks) -> None:
        """No push and no handoff, whatever else these ticks decided.

        The whole of what a retraction has to buy. A reply that is not the
        command is guidance and the developer IS resumed against it -- that
        is what the notice on this side of publication offers -- so what
        distinguishes consent withdrawn from consent acted on is the branch
        this issue does not have.
        """
        for mocks in ticks:
            mocks[support.PUSH_BRANCH].assert_not_called()
        self.assertEqual(self.github.label_history, [])

    def _retracts(self, quoted: str) -> int:
        """Take the authorization back, quoting one of our markers back at us."""
        return self._reply(
            _RETRACTION.format(quoted=quoted), author=self.github._bot_login,
        )

    def _attributed(self) -> list:
        """Every comment id this issue's record claims the orchestrator wrote."""
        return self._pinned().get(_ORCHESTRATOR_IDS) or []

    _refusal_receipt = LostWriteAttributionTest._refusal_receipt

    _strand_a_refusal = LostWriteAttributionTest._strand_a_refusal


if __name__ == "__main__":
    unittest.main()
