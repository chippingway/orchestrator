# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a squash does on an install with the size gate switched off.

`DECOMPOSE=off` decides what ENTERS the gate, and a squash is new work by that
definition: the commit it publishes is one it makes itself, out of commits a
reviewer approved. So the whole of what such an install does to make one is
squash and push: no pull request is read, none of the entry's refusals can be
taken, no reading is taken over the commit it made, and the force-push is
pinned to the head this stage read for itself -- which is the second answer
that makes the skipped reading safe, since a remote somebody moved rejects the
lease.

The road with no push behind it has no second answer, and the switch does not
reach that one: a recovery that drops a record and hands the branch back reads
the publication whatever the switch says.

`reconciling` cannot answer that question, which is why the seam asks it
separately: the squash sets that flag to say no developer ran on the tick, and
the gate reads it as answering a reading the gate itself recorded.
"""
from __future__ import annotations

import unittest

from tests.git.publication import squash_git_support as squash_support
from tests.git.publication.squash_gate_support import (
    SQUASH_PR_NUMBER,
    PublicationSeed,
)
from tests.git.publication.squash_recovery_support import (
    MOVED_HEAD,
    SQUASH_ON_APPROVAL,
    SquashRecoveryMixin,
    _CommitsWhileThePullRequestIsRead,
)
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


class SquashRecoveredSwitchedOffRealGitTest(
    SquashRecoveryMixin,
    squash_support.SquashGitFixtureMixin,
    unittest.TestCase,
):
    """The other thing the switch does not turn off.

    A collapse an interrupted tick left is unpublished work whichever way the
    gate is set, and an install with the gate off has no record of a reading
    to fall back on -- so the terms are written and read back there exactly as
    they are anywhere else.

    Nor is the reading behind a record this recovery DROPS. That road hands
    the branch on without pushing anything, so the lease that makes the
    switch's short-circuit safe everywhere else does not exist on it: the pull
    request is read whatever the switch says, and the checkout is proved again
    once that reading comes back.
    """

    def test_a_moved_remote_still_refuses(self) -> None:
        # The reading the switch may not save. This road publishes NOTHING:
        # the recovery finds the reset never ran, drops the only evidence a
        # squash was begun, and reports the branch as it found it -- so with
        # no push behind it there is no lease to answer a remote somebody
        # moved, and the refusal is the last thing before `documenting` has
        # the issue.
        gate = self._gate_subject()
        accepted = self._head_sha()
        self._crashes_before_the_reset(gate)
        gate.gh.get_pr(SQUASH_PR_NUMBER).head.sha = MOVED_HEAD

        squash_run = self._squashes(self._next_tick(gate), **{
            SQUASH_ON_APPROVAL: False, DECOMPOSE: False,
        })

        self.assertFalse(squash_run.success)
        self.assertIsNotNone(squash_run.error)
        squash_run.push_mock.assert_not_called()
        self.assertEqual(self._head_sha(), accepted)
        self._assert_branch_carries(SQUASHED_COMMITS)

    def test_a_commit_in_that_reading_refuses(self) -> None:
        # And the checkout is proved again once the reading comes back, for
        # the reason the record write is: the read is a request, so the
        # worktree is writable for the whole of it. A commit landing there is
        # work no reviewer saw, and this road reports the head it planned
        # over -- so handed on it would reach the merge button as approved.
        gate = self._gate_subject()
        self._crashes_before_the_reset(gate)
        reading = _CommitsWhileThePullRequestIsRead(self, gate)

        with reading.held():
            squash_run = self._squashes(self._next_tick(gate), **{
                SQUASH_ON_APPROVAL: False, DECOMPOSE: False,
            })

        self.assertFalse(squash_run.success)
        self.assertIsNotNone(squash_run.error)
        squash_run.push_mock.assert_not_called()
        self._assert_branch_carries(SQUASHED_COMMITS + 1)

    def test_an_unpushed_collapse_is_still_published(self) -> None:
        gate = self._gate_subject()
        original_head = self._head_sha()
        self._crashes_after_the_commit(gate)
        squashed = self._head_sha()

        squash_run = self._squashes(
            self._next_tick(gate), **{DECOMPOSE: False},
        )

        self.assertTrue(squash_run.success)
        self.assertEqual(squash_run.count, SQUASHED_COMMITS)
        pushed = squash_run.push_mock.call_args.kwargs
        self.assertEqual(pushed[REVISION], squashed)
        self.assertEqual(pushed[LEASE], original_head)


if __name__ == "__main__":
    unittest.main()
