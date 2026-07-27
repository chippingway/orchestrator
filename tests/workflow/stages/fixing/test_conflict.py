# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Tests for fixing conflict behavior."""

from __future__ import annotations

import unittest

from tests.workflow.stages.fixing import (
    fixing_routing_test_support as support,
)

CONFLICT_FIXTURE_ISSUE = support.CONFLICT_FIXTURE_ISSUE
LABEL_RESOLVING_CONFLICT = support.LABEL_RESOLVING_CONFLICT
LABEL_VALIDATING = support.LABEL_VALIDATING
MagicMock = support.MagicMock
_FixingConflictFixtureMixin = support._FixingConflictFixtureMixin
_patch_base_sync = support._patch_base_sync
workflow = support.workflow


class FixingConflictDetourTest(
    _FixingConflictFixtureMixin,
    unittest.TestCase,
):
    def test_clean_rebase_keeps_pending_feedback(self) -> None:
        # A clean refresh-time rebase now routes the `fixing` issue to
        # `validating` (no longer to `resolving_conflict`). Either way
        # the pending-fix bookmarks and in_review watermarks must
        # survive the relabel.
        self._seed_fixing_with_pending_feedback()
        rebase = MagicMock(return_value=(True, []))
        push = MagicMock(return_value=True)
        with _patch_base_sync(
            dirty=MagicMock(return_value=[]),
            rebase=rebase,
            push=push,
            head_sha=MagicMock(side_effect=["before", "after"]),
            git=MagicMock(return_value=self._git_result(stdout="3\n")),
        ):
            workflow._sync_worktree_with_base(
                self.gh,
                self.spec,
                self.wt,
                CONFLICT_FIXTURE_ISSUE,
            )

        # Clean rebase routed `fixing` straight to `validating`.
        self.assertIn((CONFLICT_FIXTURE_ISSUE, LABEL_VALIDATING), self.gh.label_history)
        self.assertNotIn((CONFLICT_FIXTURE_ISSUE, LABEL_RESOLVING_CONFLICT), self.gh.label_history)
        self._assert_pending_feedback_intact()

    def test_conflict_rebase_keeps_pending_feedback(self) -> None:
        # A conflicting refresh-time rebase still routes to
        # `resolving_conflict` so the handler can drive the dev agent.
        # The pending-fix bookmarks and watermarks must survive that
        # relabel too.
        self._seed_fixing_with_pending_feedback()
        push = MagicMock()
        with _patch_base_sync(
            dirty=MagicMock(return_value=[]),
            rebase=MagicMock(return_value=(False, ["src/feature.py"])),
            push=push,
            head_sha=MagicMock(return_value="before"),
            hardened=MagicMock(return_value=self._git_result()),
            git=MagicMock(return_value=self._git_result(stdout="3\n")),
        ):
            workflow._sync_worktree_with_base(
                self.gh,
                self.spec,
                self.wt,
                CONFLICT_FIXTURE_ISSUE,
            )

        self.assertIn((CONFLICT_FIXTURE_ISSUE, LABEL_RESOLVING_CONFLICT), self.gh.label_history)
        self.assertNotIn((CONFLICT_FIXTURE_ISSUE, LABEL_VALIDATING), self.gh.label_history)
        push.assert_not_called()
        self._assert_pending_feedback_intact()
