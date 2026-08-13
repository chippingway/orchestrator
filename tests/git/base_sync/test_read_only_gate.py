# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The per-tick base refresh leaves both read-only stages' checkouts alone.

Neither stage ever pushes, so a checkout under one of their labels is
something to read rather than work in progress -- an inspection target an
unsafe park left an operator, and, in the discussion stage which preserves its
tree on every exit, the state the next round is meant to open on. The refresh
runs before any handler does, so without this gate a tick would rebase
`origin/<base>` over that tree, and it would do it on exactly the parked issues
the handlers themselves never touch again.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from orchestrator.git.base_sync import refresh

from tests.git.base_sync.sync_test_support import _patch_base_sync
from tests.support.fakes import FakeGitHubClient, make_issue
from tests.workflow.fixtures import (
    LABEL_DISCUSSION,
    LABEL_IMPLEMENTING,
    LABEL_QUESTION,
    _TEST_SPEC,
)

_BASE_REFRESH_ISSUE_NUMBER = 980
_RELABELED_ISSUE_NUMBER = 984
_UNSPENT_BASELINE_ISSUE_NUMBER = 987
_CONSUMED_PARK_ISSUE_NUMBER = 988
_CERTIFIED_TIP = "head-the-relabel-certified"
_WORKTREE_ROOT = "/tmp/read-only-issue-"
_READ_ONLY_LABELS = (LABEL_QUESTION, LABEL_DISCUSSION)
# Both the clean hand-back and the refusal have to hold the branch still: the
# refusal names a reset target, and a rebase would move it out from under the
# operator following that instruction.
_UNCONSUMED_PARKS = (
    "discussion_response",
    "discussion_unsafe_relabel",
    "question_commits",
)


class ReadOnlyLabelBaseRefreshSkipTest(unittest.TestCase):

    def test_a_read_only_label_skips_base_sync(self) -> None:
        for offset, label in enumerate(_READ_ONLY_LABELS):
            with self.subTest(label=label):
                self._assert_skipped(_BASE_REFRESH_ISSUE_NUMBER + offset, label)

    def test_an_unconsumed_park_outlives_its_label(self) -> None:
        # The relabel to implementing takes the label away a whole tick before
        # the implementing guard reads the park: the refresh runs first. A
        # rebase in that window moves the branch off the SHA the round
        # recorded, so the guard convicts a branch nobody touched -- and its
        # refusal asks for a reset back to that same SHA, which only hands the
        # next tick the same rebase to redo. The park is what holds the
        # checkout still until the guard has answered for it.
        for offset, park_reason in enumerate(_UNCONSUMED_PARKS):
            with self.subTest(park_reason=park_reason):
                issue_number = _RELABELED_ISSUE_NUMBER + offset
                self._assert_skipped(
                    issue_number,
                    LABEL_IMPLEMENTING,
                    awaiting_human=True,
                    park_reason=park_reason,
                )

    def test_an_unspent_baseline_holds_the_branch(self) -> None:
        # The park is gone -- the guard accepted the relabel -- but the dev it
        # handed to answered with a question, or was cut short, without
        # committing. The certified tip is still what the next spawn measures
        # against, so a rebase here would move the branch off it while the
        # inherited commits it names are still there, and the spawn path would
        # read them as an interrupted dev run and publish them with no agent
        # having run at all.
        self._assert_skipped(
            _UNSPENT_BASELINE_ISSUE_NUMBER,
            LABEL_IMPLEMENTING,
            awaiting_human=True,
            park_reason="agent_question",
            read_only_baseline_sha=_CERTIFIED_TIP,
        )

    def test_a_consumed_park_syncs_again(self) -> None:
        # The guard cleared the park and persisted it, so nothing is holding
        # the branch any more and the ordinary base sync resumes. Without this
        # the freeze would be permanent for every issue that ever passed
        # through a read-only stage.
        gh = FakeGitHubClient()
        issue = make_issue(_CONSUMED_PARK_ISSUE_NUMBER, label=LABEL_IMPLEMENTING)
        gh.add_issue(issue)
        gh.seed_state(
            issue.number, awaiting_human=False, park_reason=None,
        )

        git_mock = MagicMock(return_value=MagicMock(returncode=0, stdout="0"))
        with _patch_base_sync(
            git=git_mock,
            dirty=MagicMock(return_value=[]),
            rebase=MagicMock(return_value=(True, [])),
        ):
            refresh._sync_worktree_with_base(
                gh,
                _TEST_SPEC,
                Path(f"{_WORKTREE_ROOT}{issue.number}"),
                issue.number,
            )

        git_mock.assert_called()

    def _assert_skipped(
        self, issue_number: int, label: str, **seeded,
    ) -> None:
        gh = FakeGitHubClient()
        issue = make_issue(issue_number, label=label)
        gh.add_issue(issue)
        if seeded:
            gh.seed_state(issue.number, **seeded)

        # The rev-list and rebase helpers would shell out if reached, so a
        # regression that lets the sync proceed surfaces as a call on these.
        git_mock = MagicMock()
        rebase_mock = MagicMock(return_value=(True, []))
        with _patch_base_sync(
            git=git_mock,
            dirty=MagicMock(return_value=[]),
            rebase=rebase_mock,
        ):
            refresh._sync_worktree_with_base(
                gh,
                _TEST_SPEC,
                Path(f"{_WORKTREE_ROOT}{issue.number}"),
                issue.number,
            )

        git_mock.assert_not_called()
        rebase_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
