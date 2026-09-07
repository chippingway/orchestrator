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

from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.verification.probes import _WorktreeStatus
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.workflow.stages.implementing import (
    disposition as _disposition,
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


if __name__ == "__main__":
    unittest.main()
