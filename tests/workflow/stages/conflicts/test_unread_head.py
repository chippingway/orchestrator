# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A head this stage could not read, on each seam that has to name one.

Two different facts hang off one `git rev-parse HEAD`, and neither is
bookkeeping this stage can go on without.

The head a round BEGINS at is what its publication leases the force-push
against. The size gate reads "no head" as a caller that established none, and
pins the push to whatever the pull request is standing on when IT looks --
which is after the rebase, or after an agent that was out for minutes. A commit
somebody else landed in that window becomes the lease and is force-overwritten
by work never proved against it.

The head a recovered push LEAVES the branch on is what the round it finishes is
recorded under: in the audit event, and in the receipt a size-gate hold leaves
for the tick that resumes behind the adjudication. The receipt outlives the
tick, so a push that recorded `("recovered_push", "")` and crashed before its
tail would come back to a pair no later tick can prove -- on a branch that is
in sync by then, so the round a push really landed is reported as the no-op
flip instead.

So a reading that failed stops the tick on every one of them, before anything
is rebased, resumed, or pushed.

What it does NOT do is wait for a human. A reading that did not happen is not
a question anybody can answer -- what clears it is the same reading taken
again -- so the park it leaves is retried by every tick after it rather than
consumed as a reply this issue is waiting on, and it is announced once so the
retries do not bury the notice.
"""
from __future__ import annotations

import unittest

from orchestrator.git.measurement.models import FrozenCommit

from tests.workflow.stages.conflicts.conflicts_test_support import (
    CONFLICT_PR_HEAD_SHA,
    MOVED_PR_HEAD_SHA,
    RESOLVED_HEAD_SHA,
    _ResolvingConflictMixin,
)

CONFLICT_ISSUE = 200
CONFLICT_FILE = "a.py"

BEFORE_HEAD = CONFLICT_PR_HEAD_SHA
MERGED_HEAD = RESOLVED_HEAD_SHA

# What a `git rev-parse HEAD` that established nothing answers with. It is not
# the probe the size gate proves the checkout by, so a checkout can refuse this
# reading and still be one the gate would happily push.
UNREADABLE = ""

# The head an interrupted tick left on the branch and never pushed.
RECOVERED_HEAD = "1ec04e5e" * 5

# What `git rev-list --count HEAD..origin/<base>` answers for recovered
# commits that already carry their base, which is what makes the push below a
# round of its own rather than the preamble to a rebase -- and for ones that
# do not, where the rebase behind the push owns the round instead.
ON_BASE = "0\n"
BEHIND_BASE = "2\n"

# A commit something wrote to the worktree between this stage's reading and
# the gate's own, which is the window naming the candidate closes.
MOVED_CHECKOUT = "m0vedc0m" * 5

LABEL_VALIDATING = "workflow:validating"

PUSH_BRANCH = "_push_branch"
RUN_AGENT = "run_agent"
COUNT_ADDED_LINES = "_count_added_lines"

AWAITING_HUMAN = "awaiting_human"
SETTLED_OUTCOME = "conflict_settled_outcome"
SETTLED_SHA = "conflict_settled_sha"
USER_CONTENT_HASH = "user_content_hash"

EVENT = "event"
REASON = "reason"
PARK_EVENT = "park_awaiting_human"
PARK_UNREADABLE_HEAD = "unreadable_head"
PARK_REASON = "park_reason"

# The head a repaired checkout reads as, and the head its rebase leaves.
REPAIRED_HEAD = "beef1234" * 5


class _UnreadHeadMixin(_ResolvingConflictMixin):
    """One tick over a checkout that could not name the head it stands on."""

    def _entered(self, before: str, *, pr_head: str = "", **run_options):
        """One tick begun from a checkout whose head reads as `before`."""
        github, issue = self._seed()[:2]
        if pr_head:
            github.get_pr(self.pr_number).head.sha = pr_head
        run_options.setdefault("head_shas", [before, MERGED_HEAD])
        mocks, merge = self._run_with_merge(
            github, issue, push_branch=True, **run_options
        )[:2]
        return github, mocks, merge

    def _assert_stopped(self, github, mocks) -> None:
        """Nothing measured, nothing pushed, and a human asked once."""
        mocks[COUNT_ADDED_LINES].assert_not_called()
        mocks[PUSH_BRANCH].assert_not_called()
        self.assertNotIn(
            (CONFLICT_ISSUE, LABEL_VALIDATING), github.label_history,
        )
        self.assertTrue(self._pinned(github)[AWAITING_HUMAN])
        self.assertEqual(
            [
                event[REASON] for event in github.recorded_events
                if event[EVENT] == PARK_EVENT
            ],
            [PARK_UNREADABLE_HEAD],
        )


class ConflictUnreadEntryHeadTest(unittest.TestCase, _UnreadHeadMixin):
    """The head a round begins at, which is the head its push is leased by."""

    def test_a_rebase_over_an_unread_head_refuses(self) -> None:
        # Waved through, the rebase runs and the push behind it is leased
        # against whatever the pull request has moved to. Refused before the
        # rebase, the checkout is not even rewritten.
        github, mocks, merge = self._entered(UNREADABLE)

        self._assert_stopped(github, mocks)
        merge.assert_not_called()

    def test_an_unread_head_refuses_a_moved_pr(self) -> None:
        # The move the lease exists to catch, with nothing left to catch it:
        # the caller names no head, so the gate freezes the moved one and pins
        # the push to it.
        github, mocks = self._entered(
            UNREADABLE, pr_head=MOVED_PR_HEAD_SHA,
        )[:2]

        self._assert_stopped(github, mocks)

    def test_an_unread_head_refuses_a_resolution(self) -> None:
        # The other exit of the same round. The dev is never spawned either: a
        # checkout nobody could read is not one to resolve conflicts in.
        github, mocks = self._entered(
            UNREADABLE,
            merge_succeeded=False,
            conflicted_files=[CONFLICT_FILE],
        )[:2]

        self._assert_stopped(github, mocks)
        mocks[RUN_AGENT].assert_not_called()

    def test_an_unread_head_refuses_a_body_edit(self) -> None:
        # The third seam that leases by this head, and the one that consumes
        # something on its way in. Refused before the hash is refreshed and
        # before the drift comments are marked read, so the edit is still
        # there for the next tick to detect.
        github, issue = self._seed()[:2]
        self._seed_with_baseline_hash(github, issue)
        baseline = self._pinned(github)[USER_CONTENT_HASH]
        issue.body = "the requirement moved while the rebase was in flight"

        mocks = self._run_with_merge(
            github, issue, head_shas=[UNREADABLE], push_branch=True,
        )[0]

        self._assert_stopped(github, mocks)
        mocks[RUN_AGENT].assert_not_called()
        self.assertEqual(self._pinned(github)[USER_CONTENT_HASH], baseline)
        self.assertEqual(github.posted_pr_comments, [])


class ConflictUnreadRecoveryHeadTest(unittest.TestCase, _UnreadHeadMixin):
    """The head a recovered push leaves, which is the round it records."""

    def test_a_recovery_that_names_no_round_refuses(self) -> None:
        # The receipt outlives the tick, so a crash between the push and the
        # tail would come back to `("recovered_push", "")` -- unpayable, and
        # the round a push really landed is reported as the flip that
        # resolves nothing.
        github, mocks = self._entered(
            UNREADABLE,
            head_shas=[UNREADABLE],
            branch_ahead_behind=(1, 0),
            behind_base=ON_BASE,
            # The commit the gate proves the checkout to, which is one it
            # would measure and push: the two probes are not the same reading,
            # so the caller's failure is the only thing standing here.
            candidate_commit=FrozenCommit(sha=RECOVERED_HEAD),
        )[:2]

        self._assert_stopped(github, mocks)
        pinned = self._pinned(github)
        self.assertIsNone(pinned.get(SETTLED_OUTCOME))
        self.assertIsNone(pinned.get(SETTLED_SHA))


class ConflictBehindBaseRecoveryTest(unittest.TestCase, _UnreadHeadMixin):
    """A recovered push whose rebase, not itself, will own the round.

    It records no round, so nothing about a receipt applies -- but it still
    PUSHES, and what a push publishes has to be the commit that was read. The
    gate proves the checkout independently and the worktree is writable in
    between, so a push that named nothing publishes whatever landed in that
    window under a lease proved against the head the branch used to be on.
    """

    def test_a_moved_checkout_refuses_behind_base(self) -> None:
        # Unnamed, the commit that landed in the window is the one measured
        # and force-pushed, while nothing on this road ever read it.
        github, mocks = self._recovering(
            head_shas=[RECOVERED_HEAD],
            candidate_commit=FrozenCommit(sha=MOVED_CHECKOUT),
        )

        mocks[PUSH_BRANCH].assert_not_called()
        self.assertTrue(self._pinned(github)[AWAITING_HUMAN])

    def test_an_unread_head_refuses_behind_base(self) -> None:
        # And the reading that names it is required here too, not only on the
        # road that finishes a round.
        github, mocks = self._recovering(
            head_shas=[UNREADABLE],
            candidate_commit=FrozenCommit(sha=RECOVERED_HEAD),
        )

        self._assert_stopped(github, mocks)

    def _recovering(self, **run_options):
        """One recovered push over a branch that is still behind base."""
        return self._entered(
            UNREADABLE,
            branch_ahead_behind=(1, 0),
            behind_base=BEHIND_BASE,
            **run_options,
        )[:2]


class ConflictRepairedHeadTest(unittest.TestCase, _UnreadHeadMixin):
    """The retry the unread-head park advertises, once the checkout reads.

    The park sets `awaiting_human`, and a tick that read that flag as "this
    issue is waiting on somebody" would consume itself every poll -- no
    rebase, no publication, and nobody to reply since the notice asks for a
    checkout to be repaired rather than for an answer. So the reading is
    retried instead, and the round it was refused for runs.
    """

    def test_a_repaired_checkout_rebases_again(self) -> None:
        # Two ticks: the first cannot read the head and parks, the second
        # finds it repaired. Waiting instead, the issue would sit on that park
        # forever with the thing it asked for already done.
        github, mocks, merge = self._repaired()

        merge.assert_called_once()
        mocks[PUSH_BRANCH].assert_called_once()
        self.assertIn(
            (CONFLICT_ISSUE, LABEL_VALIDATING), github.label_history,
        )

    def test_a_repaired_checkout_leaves_no_park(self) -> None:
        # The round it hands to `validating` clears the flags the refusal set,
        # so the next stage is not handed an issue that reads as waiting on
        # somebody nobody is waiting for.
        github = self._repaired()[0]

        pinned = self._pinned(github)
        self.assertFalse(pinned[AWAITING_HUMAN])
        self.assertIsNone(pinned[PARK_REASON])

    def test_the_refusal_is_said_once_while_it_stands(self) -> None:
        # Retried every tick, an unread head would post a fresh notice every
        # tick and bury the one an operator has to act on.
        github = self._entered(UNREADABLE)[0]

        self._run_with_merge(
            github, github.get_issue(CONFLICT_ISSUE),
            head_shas=[UNREADABLE], push_branch=True,
        )

        self.assertEqual(
            len([
                event for event in github.recorded_events
                if event[EVENT] == PARK_EVENT
            ]),
            1,
        )

    def _repaired(self):
        """Park on a head nothing read, then run the tick it reads again."""
        github = self._entered(UNREADABLE)[0]
        return self._entered_again(github)

    def _entered_again(self, github):
        """A second tick over the same issue, with the head readable now."""
        mocks, merge = self._run_with_merge(
            github, github.get_issue(CONFLICT_ISSUE),
            head_shas=[BEFORE_HEAD, REPAIRED_HEAD],
            candidate_commit=FrozenCommit(sha=REPAIRED_HEAD),
            push_branch=True,
        )[:2]
        return github, mocks, merge


if __name__ == "__main__":
    unittest.main()
