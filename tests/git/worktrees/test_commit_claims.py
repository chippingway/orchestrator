# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a terminal pull request accounts for, and what it leaves unpublished.

The last question a branch tip the base does not carry is put to, and the only
one whose "no" deletes a commit nobody else is holding. Every case here is
about which answer the lookup turns into: a pull request that has ended
carrying this exact object id releases the branch, and everything else --
nothing carrying it, a lookup GitHub would not answer, a thread still open --
keeps it.

The reads never touch a host, so no clone is set up: the double answers the
commit lookup the way the real client does, refusals included.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git.worktrees import commit_claims
from orchestrator.git.worktrees.models import RetentionReason
from tests.git.worktrees.eligibility_test_support import (
    OPEN_PR_STATE,
    OTHER_BASE_BRANCH,
    _github,
    _pull_request,
    _reasons,
)

BRANCH = "orchestrator/acme__widget/issue-314"
PR_NUMBER = 77
TIP_SHA = "1234abcd" * 5


def _accounting(gh) -> tuple:
    """What accounts for the tip this issue's branch is standing on."""
    return commit_claims._commit_accounting(gh, BRANCH, TIP_SHA)


class CommitAccountingTest(unittest.TestCase):
    """Whether a terminal pull request exactly accounts for one branch tip."""

    def setUp(self) -> None:
        self.gh = _github()

    def test_a_terminal_request_carrying_it_accounts(self) -> None:
        # Rejected work is still published work: the commit exists in a pull
        # request that outlives the branch, so the local copy is a copy.
        self.gh.add_pr(_pull_request(PR_NUMBER, BRANCH, TIP_SHA))

        self.assertEqual(_accounting(self.gh), ())

    def test_a_request_onto_another_base_accounts(self) -> None:
        # What makes the commit safe to delete here is that GitHub holds it,
        # which a pull request retargeted onto another base does just as well.
        self.gh.add_pr(_pull_request(
            PR_NUMBER, BRANCH, TIP_SHA, base=OTHER_BASE_BRANCH,
        ))

        self.assertEqual(_accounting(self.gh), ())

    def test_a_tip_nothing_carries_is_unaccounted(self) -> None:
        self.assertEqual(
            _reasons(_accounting(self.gh)),
            (RetentionReason.UNACCOUNTED_COMMITS,),
        )

    def test_an_unlistable_branch_is_not_an_absence(self) -> None:
        # The reading that deletes an unpublished branch if it is taken for a
        # no, which is why the lookup has an answer of its own for it.
        self.gh.unreadable_pr_lookups.add(BRANCH)

        self.assertEqual(
            _reasons(_accounting(self.gh)),
            (RetentionReason.PULL_REQUEST_UNREADABLE,),
        )

    def test_a_lookup_that_raised_is_the_same(self) -> None:
        with patch.object(
            self.gh, "find_pr_for_commit", side_effect=RuntimeError("no"),
        ):
            self.assertEqual(
                _reasons(_accounting(self.gh)),
                (RetentionReason.PULL_REQUEST_UNREADABLE,),
            )

    def test_a_request_still_open_accounts_for_none(self) -> None:
        # A disagreement between two readings of the same remote is not one
        # to settle in favour of deleting.
        self.gh.add_pr(_pull_request(
            PR_NUMBER, BRANCH, TIP_SHA, state=OPEN_PR_STATE,
        ))

        self.assertEqual(
            _reasons(_accounting(self.gh)),
            (RetentionReason.OPEN_PULL_REQUEST,),
        )


if __name__ == "__main__":
    unittest.main()
