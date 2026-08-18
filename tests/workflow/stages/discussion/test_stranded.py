# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a discussion tick does when the checkout is already holding something.

Every park this stage writes suppresses the next tick, so uncommitted work
waiting at the top of a tick can only have come from a round that died before
it could park on what it wrote. Preparing the checkout is what would destroy
it -- `_ensure_worktree` force-removes a dirty tree that carries no commits --
so the preflight runs first and the tick parks instead of spawning.

A tree that could not be READ is the same preflight's other refusal, and the
destructive step behind it is why: nothing has been established about such a
tree, and a probe that never ran answers with the same emptiness a clean one
does.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from orchestrator import config

from tests.workflow.fixtures import (
    BASE_TIP_SHA,
    KEY_AWAITING_HUMAN,
    KEY_PARK_REASON,
    _agent,
)
from tests.workflow.git_owners import seam_patch

from tests.workflow.stages.discussion.discussion_test_support import (
    DIRTY_FILE_COUNT,
    DISCUSSION_RESPONSE,
    ENSURE_PR_WORKTREE,
    ENSURE_WORKTREE,
    PARK_DISCUSSION_STRANDED,
    PARK_DISCUSSION_UNREADABLE,
    RUN_AGENT,
    WORKTREE_PATH,
)
from tests.workflow.stages.discussion.discussion_test_support import (
    DISCUSSION_SESSION,
    HEAD_AFTER_COMMIT,
    HEAD_BEFORE_ROUND,
    KEY_BASE_SHA,
    KEY_DISCUSSION_SESSION_ID,
    KEY_ROUND_BRANCH,
    KEY_ROUND_OPEN,
    KEY_ROUND_SHA,
)
from tests.workflow.stages.discussion.discussion_test_support import (
    _DiscussionWorkflowMixin,
    _dirty_files,
    _issue_branch,
    _seed_discussion,
)

_STRANDED_ISSUE_NUMBER = 970
_MISSING_TREE_ISSUE_NUMBER = 971
_UNREADABLE_TREE_ISSUE_NUMBER = 972
_UNREADABLE_HEAD_ISSUE_NUMBER = 973
_ABSENT_TREE = Path(tempfile.gettempdir()) / "orchestrator-test-absent-tree"
_UNREADABLE_CHECKOUT = "could not be read (`git status` or `HEAD` failed)"


class DiscussionStrandedWorktreeTest(unittest.TestCase, _DiscussionWorkflowMixin):

    def test_a_stranded_checkout_parks_unspawned(self) -> None:
        gh, issue = _seed_discussion(_STRANDED_ISSUE_NUMBER)

        with tempfile.TemporaryDirectory() as existing_tree:
            mocks = self._run_on_worktree(gh, issue, Path(existing_tree))

        # The checkout is neither recreated nor torn down, so the changes the
        # dead round left are still there for the operator to read.
        mocks[ENSURE_WORKTREE].assert_not_called()
        self.assert_worktree_preserved(mocks)
        # No agent ran: this tick spends nothing to reach its conclusion.
        mocks[RUN_AGENT].assert_not_called()
        self._assert_stranded_park(gh, issue.number)

    def test_a_missing_checkout_opens_the_round(self) -> None:
        # The probe answers "nothing stranded" for a checkout that is not on
        # disk at all, which is what a first-ever discussion tick finds. The
        # dirty seam is left armed to prove the preflight gates on the tree's
        # existence rather than on the probe alone.
        gh, issue = _seed_discussion(_MISSING_TREE_ISSUE_NUMBER)

        mocks = self._run_on_worktree(gh, issue, _ABSENT_TREE)

        mocks[ENSURE_WORKTREE].assert_called_once()
        mocks[RUN_AGENT].assert_called_once()

    def test_an_unreadable_checkout_parks_unspawned(self) -> None:
        # `git status` could not report on the tree at all -- a corrupt index,
        # a half-removed directory. The list form of that read maps its own
        # failure to no paths, which is exactly what a clean tree reports, so
        # the round would open and `_ensure_worktree` would force-remove the
        # one tree an operator needs to look at to find out what failed.
        gh, issue = _seed_discussion(_UNREADABLE_TREE_ISSUE_NUMBER)

        with tempfile.TemporaryDirectory() as existing_tree:
            mocks = self._run_on_worktree(
                gh,
                issue,
                Path(existing_tree),
                tree_readable=False,
                dirty_files=(),
            )

        # Neither restorer ran, so the tree is exactly as it was found.
        mocks[ENSURE_WORKTREE].assert_not_called()
        mocks[ENSURE_PR_WORKTREE].assert_not_called()
        self.assert_worktree_preserved(mocks)
        mocks[RUN_AGENT].assert_not_called()
        self.assert_nothing_published(gh, mocks)
        self.assertIn(
            _UNREADABLE_CHECKOUT,
            self._assert_park(gh, issue.number, PARK_DISCUSSION_UNREADABLE),
        )

    def test_an_unreadable_head_holds_the_anchor(self) -> None:
        # The other half of the same read, and the one with a publication
        # behind it. `rev-parse` failed for the anchor comparison alone, and
        # empty compares unequal to every anchor there is -- so the tick reads
        # "a round of ours committed here", finds the plan-shaped commit the
        # branch arrived carrying, and puts it on a pull request under a
        # session that never wrote it.
        gh, issue = _seed_discussion(_UNREADABLE_HEAD_ISSUE_NUMBER)
        gh.seed_state(
            issue.number,
            **{
                KEY_ROUND_BRANCH: _issue_branch(_UNREADABLE_HEAD_ISSUE_NUMBER),
                KEY_ROUND_SHA: HEAD_BEFORE_ROUND,
                KEY_ROUND_OPEN: True,
                KEY_BASE_SHA: BASE_TIP_SHA,
                KEY_DISCUSSION_SESSION_ID: DISCUSSION_SESSION,
            },
        )

        with tempfile.TemporaryDirectory() as existing_tree:
            mocks = self._run_on_worktree(
                gh,
                issue,
                Path(existing_tree),
                dirty_files=(),
                head_shas=("", HEAD_AFTER_COMMIT, HEAD_AFTER_COMMIT),
                committed_paths=(
                    self.plan_path(_UNREADABLE_HEAD_ISSUE_NUMBER),
                ),
            )

        mocks[RUN_AGENT].assert_not_called()
        self.assert_nothing_published(gh, mocks)
        self.assertIn(
            _UNREADABLE_CHECKOUT,
            self._assert_park(gh, issue.number, PARK_DISCUSSION_UNREADABLE),
        )

    def _run_on_worktree(self, gh, issue, worktree: Path, **overrides):
        """Run one tick against a chosen checkout, with the tree reading dirty."""
        run_options = {
            "run_agent": _agent(last_message=DISCUSSION_RESPONSE),
            "dirty_files": _dirty_files(),
        }
        run_options.update(overrides)
        with seam_patch(WORKTREE_PATH, MagicMock(return_value=worktree)):
            return self._run_discussion(gh, issue, **run_options)

    def _assert_stranded_park(self, gh, issue_number: int) -> None:
        self.assertIn(
            f"{DIRTY_FILE_COUNT} uncommitted change(s)",
            self._assert_park(gh, issue_number, PARK_DISCUSSION_STRANDED),
        )

    def _assert_park(self, gh, issue_number: int, reason: str) -> str:
        """The tick parked under `reason`; hand back what it told the human."""
        pinned_data = gh.pinned_data(issue_number)
        self.assertTrue(pinned_data[KEY_AWAITING_HUMAN])
        self.assertEqual(pinned_data[KEY_PARK_REASON], reason)
        self.assertEqual(len(gh.posted_comments), 1)
        _, body = gh.posted_comments[0]
        self.assertIn(config.HITL_MENTIONS, body)
        return body


if __name__ == "__main__":
    unittest.main()
