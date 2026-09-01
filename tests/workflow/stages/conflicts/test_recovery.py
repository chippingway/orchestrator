# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from orchestrator.git import commands as _git_commands
from orchestrator.git.base_sync import pre_pr as _base_sync_pre_pr
from orchestrator.git.measurement.models import FrozenCommit
from tests.support.publication import LandingPush
from tests.workflow.fixtures import (
    _agent,
)
from tests.workflow.stages.conflicts.conflicts_test_support import (
    RESOLVED_HEAD_SHA,
    _ResolvingConflictMixin,
)

CONFLICT_ISSUE = 200

# The commit the recovered push publishes, and the one the rebase behind it
# rewrites it into: two pushes in one tick carry two commits, which is what
# tells a second push from the receipt of the first.
RECOVERED_CANDIDATE = "1ec04e5e" * 5
REBASED_CANDIDATE = "5eba5ed1" * 5
# What the checkout stands on once the rebase has rewritten the recovered
# commit, which is what the second push is named against and leased by.
REBASED_SHA = REBASED_CANDIDATE


def _assert_completed_round(test_case, github) -> None:
    state = github.pinned_data(CONFLICT_ISSUE)
    test_case.assertEqual(state.get("review_round"), 0)
    test_case.assertEqual(state.get("conflict_round"), 1)
    test_case.assertIn("last_conflict_resolved_at", state)


def _assert_combined_round_event(test_case, github) -> None:
    rounds = [
        event
        for event in github.recorded_events
        if event.get("event") == "conflict_round" and event.get("action") == "incremented"
    ]
    test_case.assertEqual(len(rounds), 1)
    test_case.assertEqual(rounds[0].get("outcome"), "base_rebased_clean")


class ResolvingConflictRecoveryPushTest(unittest.TestCase, _ResolvingConflictMixin):
    """Drive `_handle_resolving_conflict` through the crash-recovery push
    branches: an unpushed local commit ships on the next tick, a failed
    recovery push parks, and a recovered push onto a stale base falls
    through to the rebase path for a single combined round.
    """

    def test_recovery_pushes_local_commits(self) -> None:
        # Crash recovery: a previous tick committed a conflict resolution
        # but crashed before `_push_branch` returned (or before the post-
        # push state write landed). The next tick must push the local
        # commit and complete the round, NOT treat it as "no work needed"
        # and flip to validating with the resolution unpushed.
        gh, issue, _ = self._seed()

        merge_mock = MagicMock(return_value=(True, []))
        # Before the recovered push the handler probes whether the
        # worktree is still behind base via `git rev-list --count
        # HEAD..origin/<base>` -- the reading is the same either side of a
        # push, and taken first it says which round a held candidate would
        # owe. The crash-recovery scenario this test exercises has HEAD
        # already on base, so the probe returns 0 and the handler takes the
        # fast path to validating without a follow-up rebase.
        git_on_base = MagicMock(
            return_value=MagicMock(returncode=0, stdout="0\n", stderr=""),
        )

        with (
            patch.object(_base_sync_pre_pr, "_rebase_base_into_worktree", merge_mock),
            patch.object(_git_commands, "_git", git_on_base),
        ):
            mocks = self._run_resolving_conflict(
                gh,
                issue,
                run_agent=_agent(),
                push_branch=True,
                # HEAD ahead of `origin/<branch>` by one commit (the
                # unpushed resolution); not behind.
                branch_ahead_behind=(1, 0),
                # The recovered head this stage reads and the commit the gate
                # proves the checkout to are one read of one worktree, so the
                # push, the receipt, and the round all name the same commit.
                head_shas=[RESOLVED_HEAD_SHA, RESOLVED_HEAD_SHA],
            )
        # Recovered work pushed; rebase NOT attempted (we already have a
        # resolution waiting to ship).
        mocks["_push_branch"].assert_called_once()
        merge_mock.assert_not_called()
        # No agent spawn -- the recovery is a pure push, the dev already
        # produced the commit on the previous tick.
        mocks["run_agent"].assert_not_called()
        # Round completed: counter incremented, label flipped, marker
        # stamped exactly as on the happy-path resolve. The recovered
        # push hands straight back to `validating`; the single docs
        # pass is deferred to the post-approval hop.
        _assert_completed_round(self, gh)
        self.assertIn((CONFLICT_ISSUE, "workflow:validating"), gh.label_history)
        self.assertNotIn((CONFLICT_ISSUE, "workflow:documenting"), gh.label_history)

    def test_unpushed_recovery_push_failure_parks(self) -> None:
        # Recovery push fails (e.g. force-with-lease lease miss because
        # the remote actually moved). Park rather than silently flipping
        # to validating with an unsynced local SHA.
        gh, issue, _ = self._seed()

        merge_mock = MagicMock(return_value=(True, []))
        # The behind-base probe runs BEFORE the push, because the round a
        # held candidate would owe has to be decided while the gate can still
        # be told about it. On base here, so this push would have completed
        # the round had it landed.
        git_on_base = MagicMock(
            return_value=MagicMock(returncode=0, stdout="0\n", stderr=""),
        )

        with (
            patch.object(_base_sync_pre_pr, "_rebase_base_into_worktree", merge_mock),
            patch.object(_git_commands, "_git", git_on_base),
        ):
            mocks = self._run_resolving_conflict(
                gh,
                issue,
                run_agent=_agent(),
                push_branch=False,
                branch_ahead_behind=(1, 0),
                head_shas=[RESOLVED_HEAD_SHA, RESOLVED_HEAD_SHA],
            )
        mocks["_push_branch"].assert_called_once()
        merge_mock.assert_not_called()
        self.assertTrue(gh.pinned_data(CONFLICT_ISSUE).get("awaiting_human"))
        self.assertNotIn((CONFLICT_ISSUE, "workflow:validating"), gh.label_history)

    def test_stale_base_falls_through_to_rebase(self) -> None:
        # The `fixing` drift router
        # (`_reconcile_parked_fixing`) reroutes here
        # when a stuck `push_failed` / `agent_timeout` park has
        # UNPUSHED FIX COMMITS on a base that has since advanced. The
        # recovered-push fast path would publish the fix to the PR
        # branch and flip straight to `validating` -- but the branch
        # is still behind base. Probe behind-base after the push and
        # fall through to the rebase path so the same tick integrates
        # base and consumes exactly ONE `conflict_round` for the
        # combined push+rebase reconciliation. Without this, the PR
        # would be republished still-behind-base and the round counter
        # would burn a slot toward `MAX_CONFLICT_ROUNDS` without ever
        # attempting the base rebase the reroute was meant to perform.
        gh, issue, _ = self._seed()

        # Clean rebase that actually moved HEAD (recovered push +
        # rebase pushes a different SHA than the recovered SHA).
        merge_mock = MagicMock(return_value=(True, []))
        # Probe says still 2 commits behind base after the recovered
        # push, forcing the fall-through.
        git_behind_base = MagicMock(
            return_value=MagicMock(returncode=0, stdout="2\n", stderr=""),
        )

        with (
            patch.object(_base_sync_pre_pr, "_rebase_base_into_worktree", merge_mock),
            patch.object(_git_commands, "_git", git_behind_base),
        ):
            mocks = self._run_resolving_conflict(
                gh,
                issue,
                run_agent=_agent(),
                # The recovered push lands, so the pull request stands on
                # what it published when the rebase behind it leases its own
                # push against the head that push left.
                push_branch=LandingPush(gh, self.pr_number),
                # Recovered push first, leased against the head the pull
                # request was standing on; then the rebased-head push, leased
                # against the head this stage reads back before it rebases.
                # Reading by reading: the recovered push names the commit it
                # publishes, then the rebase path compares its own before and
                # after, then the audit emit records what it left.
                branch_ahead_behind=(1, 0),
                head_shas=[
                    RECOVERED_CANDIDATE, RECOVERED_CANDIDATE,
                    REBASED_SHA, REBASED_SHA,
                ],
                # The rebase rewrites the recovered commit, so the second
                # push publishes a different one -- which is why it is a
                # push at all rather than the receipt of the first being
                # recognized. Reading by reading: the recovered push
                # measures it and then proves the checkout still on it, and
                # only the rebase behind that moves the head.
                candidate_commit=(
                    FrozenCommit(sha=RECOVERED_CANDIDATE),
                    FrozenCommit(sha=RECOVERED_CANDIDATE),
                    FrozenCommit(sha=REBASED_CANDIDATE),
                ),
            )

        # Both the recovered push AND the rebased-head push fired this
        # tick; the merge attempt ran in between.
        self.assertEqual(mocks["_push_branch"].call_count, 2)
        merge_mock.assert_called_once()
        # No agent spawn -- the rebase was clean.
        mocks["run_agent"].assert_not_called()
        # Single conflict_round increment for the combined push+rebase
        # reconciliation, NOT one per push.
        _assert_completed_round(self, gh)
        # The combined round outcome is the rebase path's
        # `base_rebased_clean`, not the fast-path `recovered_push`.
        _assert_combined_round_event(self, gh)
        # Hand back to validating after the rebase landed.
        self.assertIn((CONFLICT_ISSUE, "workflow:validating"), gh.label_history)
        self.assertNotIn((CONFLICT_ISSUE, "workflow:documenting"), gh.label_history)


if __name__ == "__main__":
    unittest.main()
