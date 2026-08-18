# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The base a round pins has to be a commit this clone can read.

Real repositories rather than mocked git, because the gap being closed is
between two real things: the id comes from the remote, the diff that spends it
runs locally, and the object store sits between them. A mock could only show
that a fetch was asked for; only git can show that a base this clone does not
hold turns a branch carrying exactly the plan into a branch that reads as
carrying nothing at all -- the same answer a branch that changed nothing gives,
which is what would refuse a plan written exactly as asked.

So each test proves that trap first, on the same repositories: the diff against
a tip the clone has never fetched is taken before the pin, and reports no paths.

The world those tests are run in -- the upstream standing in for GitHub, the
clone of it, and the two token-bearing calls redirected to reach it over a path
-- is built by the real-git support module beside this one.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from orchestrator.git.verification import probes
from orchestrator.workflow.stages.discussion import models as _models, run as _run

from tests.workflow.git_owners import seam_patch

from tests.workflow.stages.discussion.discussion_real_git_test_support import (
    PLAN_TEXT,
    UPSTREAM_DIR,
    _commit_file,
    _failed_fetch,
    _fetch_upstream,
    _real_git_spec,
    _seed_upstream_clone,
)
from tests.workflow.stages.discussion.discussion_test_support import (
    AUTHED_TARGET_FETCH,
    REMOTE_BASE_TIP,
    _issue_branch,
    _seed_discussion,
)

_ISSUE_NUMBER = 1273

LATER_FILE = "landed_after_the_clone.py"
PLAN_PATH = f"plans/issue-{_ISSUE_NUMBER}.md"
LATER_TEXT = "print('landed meanwhile')\n"
TEMP_PREFIX = "orch-discussion-base-"


class DiscussionBaseObjectTest(unittest.TestCase):
    """What `_pinned_base_sha` records once the object store is asked too."""

    def setUp(self) -> None:
        world = tempfile.TemporaryDirectory(prefix=TEMP_PREFIX)
        self.addCleanup(world.cleanup)
        root = Path(world.name)
        self.upstream = root / UPSTREAM_DIR
        self.worktree = root / f"issue-{_ISSUE_NUMBER}"
        self.spec = _real_git_spec(root)
        self._build_world()

    def test_an_absent_base_is_fetched_then_pinned(self) -> None:
        # Recorded as the remote named it and left absent, this id fails the
        # publication's own diff -- and a failed diff names no paths, so the
        # branch carrying the agreed plan is refused for carrying nothing.
        self.assertEqual(self._changed_paths(self.advanced_base), [])

        pinned = self._pin_base(self.advanced_base, _fetch_upstream)

        self.assertEqual(pinned, self.advanced_base)
        self.assertEqual(self._changed_paths(pinned), [PLAN_PATH])

    def test_a_base_in_the_store_costs_no_fetch(self) -> None:
        # The ordinary round, and why the fetch is conditional: the tick's own
        # refresh already brought this base, so asking the remote for it again
        # on every round of every conversation buys nothing.
        fetch = MagicMock(side_effect=_fetch_upstream)

        pinned = self._pin_base(self.first_base, fetch)

        self.assertEqual(pinned, self.first_base)
        fetch.assert_not_called()

    def test_a_base_no_fetch_brings_is_not_pinned(self) -> None:
        # A remote that refused us, or a base rewritten out from under the id
        # just read. Recording it anyway would spend the round on a reading
        # nobody can take: the diff fails, reports nothing, and the plan is
        # refused for it. No base is the honest record, and the publication
        # check refuses on that one and says so.
        self.assertEqual(self._pin_base(self.advanced_base, _failed_fetch), "")

    def _pin_base(self, remote_tip: str, fetch) -> str:
        """Pin one round's base, with both token-bearing calls redirected."""
        gh, issue = _seed_discussion(_ISSUE_NUMBER)
        run = _models._DiscussionRun.start(gh, self.spec, issue)
        with (
            seam_patch(REMOTE_BASE_TIP, MagicMock(return_value=remote_tip)),
            seam_patch(AUTHED_TARGET_FETCH, fetch),
        ):
            return _run._pinned_base_sha(run, self.worktree)

    def _changed_paths(self, base_sha: str) -> list[str]:
        """What the plan commit changes against `base_sha`, as read locally."""
        return probes._committed_paths_since(
            self.worktree, base_sha, self.plan_head,
        )

    def _build_world(self) -> None:
        """An upstream on its base branch, a clone of it, and one checkout."""
        self.first_base = _seed_upstream_clone(
            self.spec,
            self.upstream,
            self.worktree,
            _issue_branch(_ISSUE_NUMBER),
        )
        # The base moves on after the clone, which is the window every round
        # opens in: the tick fetched once, and a sibling PR merged since.
        self.advanced_base = _commit_file(self.upstream, LATER_FILE, LATER_TEXT)
        self.plan_head = _commit_file(self.worktree, PLAN_PATH, PLAN_TEXT)


if __name__ == "__main__":
    unittest.main()
