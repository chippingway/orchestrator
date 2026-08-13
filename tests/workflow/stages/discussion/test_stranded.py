# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a discussion tick does when the checkout is already holding something.

Every park this stage writes suppresses the next tick, so uncommitted work
waiting at the top of a tick can only have come from a round that died before
it could park on what it wrote. Preparing the checkout is what would destroy
it -- `_ensure_worktree` force-removes a dirty tree that carries no commits --
so the preflight runs first and the tick parks instead of spawning.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from orchestrator import config

from tests.workflow.fixtures import (
    KEY_AWAITING_HUMAN,
    KEY_PARK_REASON,
    _agent,
)
from tests.workflow.git_owners import seam_patch

from tests.workflow.stages.discussion.discussion_test_support import (
    DIRTY_FILE_COUNT,
    DISCUSSION_RESPONSE,
    ENSURE_WORKTREE,
    PARK_DISCUSSION_STRANDED,
    RUN_AGENT,
    WORKTREE_PATH,
)
from tests.workflow.stages.discussion.discussion_test_support import (
    _DiscussionWorkflowMixin,
    _dirty_files,
    _seed_discussion,
)

_STRANDED_ISSUE_NUMBER = 970
_MISSING_TREE_ISSUE_NUMBER = 971
_ABSENT_TREE = Path(tempfile.gettempdir()) / "orchestrator-test-absent-tree"


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

    def _run_on_worktree(self, gh, issue, worktree: Path):
        """Run one tick against a chosen checkout, with the tree reading dirty."""
        with seam_patch(WORKTREE_PATH, MagicMock(return_value=worktree)):
            return self._run_discussion(
                gh,
                issue,
                run_agent=_agent(last_message=DISCUSSION_RESPONSE),
                dirty_files=_dirty_files(),
            )

    def _assert_stranded_park(self, gh, issue_number: int) -> None:
        pinned_data = gh.pinned_data(issue_number)
        self.assertTrue(pinned_data[KEY_AWAITING_HUMAN])
        self.assertEqual(pinned_data[KEY_PARK_REASON], PARK_DISCUSSION_STRANDED)
        self.assertEqual(len(gh.posted_comments), 1)
        _, body = gh.posted_comments[0]
        self.assertIn(config.HITL_MENTIONS, body)
        self.assertIn(f"{DIRTY_FILE_COUNT} uncommitted change(s)", body)


if __name__ == "__main__":
    unittest.main()
