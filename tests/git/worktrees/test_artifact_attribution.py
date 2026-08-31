# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which repository a local branch is charged to, and which are charged to nobody."""

from __future__ import annotations

import logging
import unittest
from pathlib import Path

from orchestrator.git.worktrees import attribution

from tests.git.worktrees.artifact_test_support import (
    COLLIDING_SLUGS,
    GADGET_SLUG,
    LIFECYCLE_LOGGER,
    STRANGER_SLUG,
    WIDGET_SLUG,
    _legacy_branch,
    _namespaced_branch,
    _spec,
)

SHARED_CLONE = Path("/tmp/orchestrator-attribution-clone")

BRANCH_ISSUE_NUMBER = 4
LEGACY_ISSUE_NUMBER = 9
BOTH_LAYOUTS_ISSUE_NUMBER = 7
COLLIDING_ISSUE_NUMBER = 3

# Names that live in the orchestrator-owned namespace and belong to none of the
# configured repositories: another repository's segment, a segment no entry
# produces, issue numbers written in forms nothing here writes, a tail buried
# one component too deep, one component too shallow, and a branch that names no
# issue at all.
UNOWNED_BRANCHES = (
    _namespaced_branch(STRANGER_SLUG, 3),
    "orchestrator/acme__gizmo/issue-3",
    "orchestrator/issue-007",
    "orchestrator/issue-0",
    "orchestrator/issue-+3",
    "orchestrator/issue-abc",
    "orchestrator/acme__widget/deep/issue-3",
    "orchestrator/acme__widget/issue-3/tail",
    "orchestrator/issue-3-fixup",
    "orchestrator/main",
)


class CurrentLayoutTest(unittest.TestCase):
    """A namespaced branch is charged to the repository that publishes it.

    The case a shared clone exists for: both repositories' branches sit in one
    ref store, and each name says which of them wrote it.
    """

    def test_each_repository_gets_its_own(self) -> None:
        widget = _spec(WIDGET_SLUG, SHARED_CLONE)
        gadget = _spec(GADGET_SLUG, SHARED_CLONE)
        widget_branch = _namespaced_branch(WIDGET_SLUG, BRANCH_ISSUE_NUMBER)
        gadget_branch = _namespaced_branch(GADGET_SLUG, BRANCH_ISSUE_NUMBER)

        owned = attribution._attributed_issues(
            (widget_branch, gadget_branch), (widget, gadget),
        )

        self.assertEqual(owned, {
            widget: {BRANCH_ISSUE_NUMBER: (widget_branch,)},
            gadget: {BRANCH_ISSUE_NUMBER: (gadget_branch,)},
        })

    def test_a_repository_with_none_is_absent(self) -> None:
        # An empty entry and a missing one read differently to a caller
        # walking the answer, so a repository nothing was found for is simply
        # not in it.
        widget = _spec(WIDGET_SLUG, SHARED_CLONE)
        gadget = _spec(GADGET_SLUG, SHARED_CLONE)

        owned = attribution._attributed_issues(
            (_namespaced_branch(WIDGET_SLUG, BRANCH_ISSUE_NUMBER),),
            (widget, gadget),
        )

        self.assertEqual(tuple(owned), (widget,))


class LegacyLayoutTest(unittest.TestCase):
    """The flat pre-namespacing branch carries no slug, so the clone decides.

    One repository on a clone owns it by elimination; several on one clone
    make it unattributable, and attributing it anyway would charge one
    repository for another's issue number.
    """

    def test_a_lone_repository_owns_it(self) -> None:
        widget = _spec(WIDGET_SLUG, SHARED_CLONE)
        legacy = _legacy_branch(LEGACY_ISSUE_NUMBER)

        owned = attribution._attributed_issues((legacy,), (widget,))

        self.assertEqual(owned, {widget: {LEGACY_ISSUE_NUMBER: (legacy,)}})

    def test_a_shared_clone_refuses_it(self) -> None:
        widget = _spec(WIDGET_SLUG, SHARED_CLONE)
        gadget = _spec(GADGET_SLUG, SHARED_CLONE)

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING) as logs:
            owned = attribution._attributed_issues(
                (_legacy_branch(LEGACY_ISSUE_NUMBER),), (widget, gadget),
            )
            refusal = logs.output[0]

        self.assertEqual(owned, {})
        # The operator gets both claimants by name: the refusal is theirs to
        # resolve, and it cannot be resolved without knowing who is claiming.
        self.assertIn(WIDGET_SLUG, refusal)
        self.assertIn(GADGET_SLUG, refusal)

    def test_both_layouts_are_one_issue(self) -> None:
        # An issue that was migrated mid-flight has a branch under each
        # layout. Two names, one issue -- and the namespaced one first,
        # because that is the one a caller acts on.
        widget = _spec(WIDGET_SLUG, SHARED_CLONE)
        namespaced = _namespaced_branch(WIDGET_SLUG, BOTH_LAYOUTS_ISSUE_NUMBER)
        legacy = _legacy_branch(BOTH_LAYOUTS_ISSUE_NUMBER)

        owned = attribution._attributed_issues((legacy, namespaced), (widget,))

        self.assertEqual(
            owned, {widget: {BOTH_LAYOUTS_ISSUE_NUMBER: (namespaced, legacy)}},
        )


class UnattributableBranchTest(unittest.TestCase):
    """Everything else in the namespace is left where it was found."""

    def test_names_nothing_publishes_are_left(self) -> None:
        widget = _spec(WIDGET_SLUG, SHARED_CLONE)
        for branch in UNOWNED_BRANCHES:
            with self.subTest(branch=branch):
                self.assertEqual(
                    attribution._attributed_issues((branch,), (widget,)), {},
                )

    def test_two_repositories_deriving_one(self) -> None:
        # The ambiguity the legacy layout has by construction, reached through
        # the current one: two `REPOS` entries whose slugs differ only in a
        # character the ref sanitizer rewrites publish under one branch name,
        # and nothing in that name says which of them wrote it.
        specs = tuple(_spec(slug, SHARED_CLONE) for slug in COLLIDING_SLUGS)
        collided = _namespaced_branch(
            COLLIDING_SLUGS[1], COLLIDING_ISSUE_NUMBER,
        )

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING):
            owned = attribution._attributed_issues((collided,), specs)

        self.assertEqual(owned, {})


class WorktreeDirectoryTest(unittest.TestCase):
    """Which repositories the path sanitizer hands one checkout directory.

    The branch rules above ask a clone; this one asks the configuration, since
    every repository's checkouts hang off one `WORKTREES_DIR` whatever clone
    it is on.
    """

    def test_a_shared_directory_refuses_both(self) -> None:
        specs = tuple(_spec(slug, SHARED_CLONE) for slug in COLLIDING_SLUGS)

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING) as logs:
            colliding = attribution._colliding_worktree_slugs(specs)
            refusal = logs.output[0]

        self.assertEqual(colliding, tuple(sorted(COLLIDING_SLUGS)))
        # Both claimants by name again: an operator resolving this has to know
        # which two entries were handed the same directory.
        for slug in COLLIDING_SLUGS:
            with self.subTest(slug=slug):
                self.assertIn(slug, refusal)

    def test_distinct_directories_are_kept(self) -> None:
        specs = (
            _spec(WIDGET_SLUG, SHARED_CLONE), _spec(GADGET_SLUG, SHARED_CLONE),
        )

        self.assertEqual(attribution._colliding_worktree_slugs(specs), ())


if __name__ == "__main__":
    unittest.main()
