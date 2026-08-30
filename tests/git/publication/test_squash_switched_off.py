# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a squash does on an install with the size gate switched off.

`DECOMPOSE=off` decides what ENTERS the gate, and a squash is new work by that
definition: the commit it publishes is one it makes itself, out of commits a
reviewer approved. So the whole of what such an install does is squash and
push: no pull request is read, none of the entry's refusals can be taken, no
reading is taken over the commit it made, and the force-push is pinned to the
head this stage read for itself.

`reconciling` cannot answer that question, which is why the seam asks it
separately: the squash sets that flag to say no developer ran on the tick, and
the gate reads it as answering a reading the gate itself recorded.
"""
from __future__ import annotations

import unittest

from tests.git.publication import squash_git_support as squash_support
from tests.git.publication.squash_gate_support import PublicationSeed
from tests.git.publication.test_squash_gate import (
    CLOSED,
    PAST_THE_CEILING,
    _MovesPastTheFirstProof,
)

MAX_ADDED_LINES = "MAX_ADDED_LINES"
DECOMPOSE = "DECOMPOSE"

# The two keywords a gated push names its commit and pins its ref by.
REVISION = "revision"
LEASE = "force_with_lease"

# What the fixture's topic branch is made of.
SQUASHED_COMMITS = 3


class SquashSwitchedOffRealGitTest(
    squash_support.SquashGitFixtureMixin,
    unittest.TestCase,
):
    """Every reading the switch keeps a squash out of, and the one it does not."""

    def test_it_reads_no_pull_request(self) -> None:
        # A closed pull request is the sharpest of the entry's refusals and
        # the one that cannot come from anywhere else: with the gate off
        # there is no reading to take it, so a pull request nobody could
        # publish onto costs this squash nothing and it goes out regardless.
        original_head = self._head_sha()

        squash_run = self._squash(
            publication=PublicationSeed(state=CLOSED),
            **{DECOMPOSE: False},
        )

        self.assertTrue(squash_run.success)
        self.assertEqual(squash_run.count, SQUASHED_COMMITS)
        pushed = squash_run.push_mock.call_args
        self.assertEqual(pushed.kwargs[REVISION], self._head_sha())
        self.assertEqual(pushed.kwargs[LEASE], original_head)

    def test_it_measures_nothing(self) -> None:
        # And no reading is taken over the commit it made either: a ceiling
        # this squash would cross is a question an install with the gate off
        # never asks.
        squash_run = self._squash(**{
            DECOMPOSE: False, MAX_ADDED_LINES: PAST_THE_CEILING,
        })

        self.assertTrue(squash_run.success)
        self.assertFalse(squash_run.held)
        squash_run.push_mock.assert_called_once()

    def test_a_moved_checkout_still_refuses(self) -> None:
        # What the switch does NOT turn off. The commit the squash made is
        # still the commit its push may publish, so a checkout something moved
        # in between refuses -- the switch decides measurement, not whether a
        # push knows which object it is sending.
        squash_run = self._squash(
            proved_heads=_MovesPastTheFirstProof(self),
            **{DECOMPOSE: False},
        )

        self.assertFalse(squash_run.success)
        squash_run.push_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
