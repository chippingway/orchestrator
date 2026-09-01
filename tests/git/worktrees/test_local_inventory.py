# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The read-only scan: which issues a host's own artifacts name, and which it refuses.

Which clone a repository is read from and what a failed read costs are driven
with the branch listing stubbed on its owner, because neither turns on what
the listing says. What a candidate is made of is driven against real clones,
real branches, and real checkouts instead: the shapes an issue can be in are
exactly what the arguments, the attribution, and the on-disk layout produce
together, so a stub of any of them would assert itself back.
"""

from __future__ import annotations

import contextlib
import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.git.worktrees import inventory, paths, probes

from tests.git.worktrees.artifact_test_support import (
    COLLIDING_SLUGS,
    GADGET_SLUG,
    LIFECYCLE_LOGGER,
    WIDGET_SLUG,
)
# The builders a world is planted with, named apart from what it is named by.
from tests.git.worktrees.artifact_test_support import (
    _ArtifactWorld,
    _block_worktrees_root,
    _break_ref,
    _legacy_branch,
    _namespaced_branch,
    _spec,
)

CLONE_NAME = "target"
SECOND_CLONE_NAME = "other-target"
CLONE_LINK_NAME = "target-link"

BOTH_SIDES_ISSUE_NUMBER = 4
CHECKOUT_ONLY_ISSUE_NUMBER = 15
LEGACY_ISSUE_NUMBER = 9
GADGET_ISSUE_NUMBER = 6

# What the scan must walk past: another repository's namespaced branch, and a
# name in the namespace that carries no issue number at all.
IGNORED_BRANCHES = (
    "orchestrator/stranger__repo/issue-5",
    "orchestrator/issue-abc",
)


@contextlib.contextmanager
def _listing(branches):
    """Answer every clone's branch listing with `branches`."""
    with patch.object(
        probes, "_local_orchestrator_branches", return_value=branches,
    ) as listed:
        yield listed


def _found(scanned):
    """Each candidate as the repository and issue it names."""
    return tuple(
        (artifacts.spec.slug, artifacts.issue_number)
        for artifacts in scanned.issues
    )


class _LoopingPath(Path):
    """A clone path whose resolution fails the way a symlink loop fails it.

    A path that raises rather than a loop planted on disk, because what a loop
    costs depends on the interpreter: `Path.resolve` raises `RuntimeError` on
    one under Python 3.12 and answers with the path itself under 3.13. What is
    asserted through this is the handling, which both of them reach.
    """

    def resolve(self, strict: bool = False) -> Path:
        raise RuntimeError(f"Symlink loop from {self}")


class CloneGroupingTest(unittest.TestCase):
    """Which clone a repository's branches are read from, and how often."""

    def setUp(self) -> None:
        self.world = _ArtifactWorld()
        self.world.prepare(self)
        self.clone = self.world.clone(CLONE_NAME)
        self.widget = _spec(WIDGET_SLUG, self.clone)

    def test_one_listing_serves_a_clone(self) -> None:
        # The specs sharing a clone share its ref store, so a second listing
        # would spend a git process to read the same refs back.
        gadget = _spec(GADGET_SLUG, self.clone)

        with _listing(()) as listed:
            inventory._local_issue_inventory((self.widget, gadget))
            listed.assert_called_once_with(self.clone)

    def test_one_clone_under_two_paths_is_one(self) -> None:
        # One clone under two spellings is still one ref store, so its legacy
        # branch has two claimants and belongs to neither. Grouped by the path
        # each spec configures, both would claim it.
        link = self.world.path(CLONE_LINK_NAME)
        link.symlink_to(self.clone)
        gadget = _spec(GADGET_SLUG, link)

        with _listing((_legacy_branch(LEGACY_ISSUE_NUMBER),)):
            scanned = inventory._local_issue_inventory((self.widget, gadget))

        self.assertEqual(scanned.issues, ())
        self.assertEqual(scanned.refused, ())


class LocalInventoryRefusalTest(unittest.TestCase):
    """What one read that could not be taken costs the rest of the answer."""

    def setUp(self) -> None:
        self.world = _ArtifactWorld()
        self.world.prepare(self)
        self.clone = self.world.clone(CLONE_NAME)
        self.widget = _spec(WIDGET_SLUG, self.clone)

    def test_an_unread_clone_refuses_all_of_it(self) -> None:
        # The checkout is right there on disk and is still not reported: what
        # a caller does with an issue turns on whether a branch is under it,
        # and an unread ref store cannot say.
        gadget = _spec(GADGET_SLUG, self.clone)
        self.world.checkout(self.widget, BOTH_SIDES_ISSUE_NUMBER)

        with _listing(None):
            scanned = inventory._local_issue_inventory((self.widget, gadget))

        self.assertEqual(scanned.issues, ())
        self.assertEqual(scanned.refused, (GADGET_SLUG, WIDGET_SLUG))

    def test_an_unresolvable_clone_refuses_one(self) -> None:
        # The refusal has to come from the grouping too: resolution runs
        # before a single repository has been read, so a root that cannot be
        # resolved would otherwise end the scan for the healthy ones with it.
        gadget = _spec(GADGET_SLUG, self.world.clone(SECOND_CLONE_NAME))
        self.world.checkout(gadget, GADGET_ISSUE_NUMBER)
        widget = _spec(WIDGET_SLUG, _LoopingPath(self.clone))

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING), _listing(()):
            scanned = inventory._local_issue_inventory((widget, gadget))

        self.assertEqual(scanned.refused, (WIDGET_SLUG,))
        self.assertEqual(_found(scanned), ((GADGET_SLUG, GADGET_ISSUE_NUMBER),))

    def test_a_shared_checkout_directory_refuses(self) -> None:
        # The sanitizer naming each repository's checkout directory is lossy
        # too, so two entries it cannot tell apart are handed one directory --
        # and the `issue-<n>` in it belongs to whichever of them created it,
        # which the directory does not record. Both are refused, and the
        # repository with a directory of its own still answers.
        gadget = _spec(GADGET_SLUG, self.world.clone(SECOND_CLONE_NAME))
        self.world.checkout(gadget, GADGET_ISSUE_NUMBER)
        colliding = tuple(_spec(slug, self.clone) for slug in COLLIDING_SLUGS)
        self.world.checkout(colliding[0], BOTH_SIDES_ISSUE_NUMBER)

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING), _listing(()):
            scanned = inventory._local_issue_inventory((*colliding, gadget))

        self.assertEqual(scanned.refused, tuple(sorted(COLLIDING_SLUGS)))
        self.assertEqual(_found(scanned), ((GADGET_SLUG, GADGET_ISSUE_NUMBER),))

    def test_a_refused_spec_still_claims_a_branch(self) -> None:
        # Refusing a repository settles what the scan REPORTS, not who could
        # have published what is on the clone. The colliding pair is still on
        # this ref store, so its flat `orchestrator/issue-<n>` has three
        # possible owners and belongs to none of them -- while the branch
        # naming a repository outright is still that repository's.
        healthy = _spec(GADGET_SLUG, self.clone)
        colliding = tuple(_spec(slug, self.clone) for slug in COLLIDING_SLUGS)
        branches = (
            _legacy_branch(LEGACY_ISSUE_NUMBER),
            _namespaced_branch(GADGET_SLUG, GADGET_ISSUE_NUMBER),
        )

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING), _listing(branches):
            scanned = inventory._local_issue_inventory(
                (*colliding, healthy),
            )

        self.assertEqual(scanned.refused, tuple(sorted(COLLIDING_SLUGS)))
        self.assertEqual(_found(scanned), ((GADGET_SLUG, GADGET_ISSUE_NUMBER),))

    def test_an_unread_root_refuses_one_repository(self) -> None:
        # The refusal is per repository: a host that cannot list one
        # repository's checkouts still answers for the rest.
        gadget = _spec(GADGET_SLUG, self.world.clone(SECOND_CLONE_NAME))
        self.world.checkout(gadget, GADGET_ISSUE_NUMBER)
        _block_worktrees_root(self.widget)

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING), _listing(()):
            scanned = inventory._local_issue_inventory((self.widget, gadget))

        self.assertEqual(scanned.refused, (WIDGET_SLUG,))
        self.assertEqual(_found(scanned), ((GADGET_SLUG, GADGET_ISSUE_NUMBER),))


class LocalInventoryRealGitTest(unittest.TestCase):
    """The whole scan against real clones, branches, and checkouts."""

    def setUp(self) -> None:
        self.world = _ArtifactWorld()
        self.world.prepare(self)
        self.clone = self.world.clone(CLONE_NAME)
        self.widget = _spec(WIDGET_SLUG, self.clone)

    def test_every_shape_on_one_clone_is_read(self) -> None:
        # The three shapes an issue reaches a scan in: a checkout with its
        # branch -- one entry, not two -- a branch whose checkout is gone, and
        # a checkout whose branch is.
        self._plant_widget_artifacts()

        scanned = inventory._local_issue_inventory((self.widget,))

        self.assertEqual(
            tuple(
                (found.issue_number, found.worktree, found.branches)
                for found in scanned.issues
            ),
            (
                (
                    BOTH_SIDES_ISSUE_NUMBER,
                    paths._worktree_path(self.widget, BOTH_SIDES_ISSUE_NUMBER),
                    (_namespaced_branch(WIDGET_SLUG, BOTH_SIDES_ISSUE_NUMBER),),
                ),
                (
                    LEGACY_ISSUE_NUMBER,
                    None,
                    (_legacy_branch(LEGACY_ISSUE_NUMBER),),
                ),
                (
                    CHECKOUT_ONLY_ISSUE_NUMBER,
                    paths._worktree_path(
                        self.widget, CHECKOUT_ONLY_ISSUE_NUMBER,
                    ),
                    (),
                ),
            ),
        )
        self.assertEqual(scanned.refused, ())

    def test_a_shared_clone_splits_by_branch(self) -> None:
        # The second entry on this clone turns the legacy branch from "the
        # only repository here" into an unanswerable question, while the
        # namespaced branches keep saying who published them.
        gadget = _spec(GADGET_SLUG, self.clone)
        self._plant_widget_artifacts()
        self.world.branch(
            self.clone, _namespaced_branch(GADGET_SLUG, GADGET_ISSUE_NUMBER),
        )

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING):
            scanned = inventory._local_issue_inventory((self.widget, gadget))

        self.assertEqual(_found(scanned), (
            (GADGET_SLUG, GADGET_ISSUE_NUMBER),
            (WIDGET_SLUG, BOTH_SIDES_ISSUE_NUMBER),
            (WIDGET_SLUG, CHECKOUT_ONLY_ISSUE_NUMBER),
        ))

    def test_several_clones_make_one_answer(self) -> None:
        gadget = _spec(GADGET_SLUG, self.world.clone(SECOND_CLONE_NAME))
        self._plant_widget_artifacts()
        self.world.branch(
            gadget.target_root,
            _namespaced_branch(GADGET_SLUG, GADGET_ISSUE_NUMBER),
        )

        scanned = inventory._local_issue_inventory((self.widget, gadget))

        self.assertEqual(_found(scanned), (
            (GADGET_SLUG, GADGET_ISSUE_NUMBER),
            (WIDGET_SLUG, BOTH_SIDES_ISSUE_NUMBER),
            (WIDGET_SLUG, LEGACY_ISSUE_NUMBER),
            (WIDGET_SLUG, CHECKOUT_ONLY_ISSUE_NUMBER),
        ))
        self.assertEqual(scanned.refused, ())

    def test_a_broken_ref_refuses_the_repository(self) -> None:
        # The whole cost of a listing that warns, end to end: the checkout is
        # on disk and its branch is the ref git skipped, so an answer built
        # from what the listing did print would report the issue as a checkout
        # whose branch is gone -- the shape a cleanup acts on.
        self.world.checkout(self.widget, BOTH_SIDES_ISSUE_NUMBER)
        _break_ref(
            self.clone, _namespaced_branch(WIDGET_SLUG, BOTH_SIDES_ISSUE_NUMBER),
        )

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING):
            scanned = inventory._local_issue_inventory((self.widget,))

        self.assertEqual(scanned.issues, ())
        self.assertEqual(scanned.refused, (WIDGET_SLUG,))

    def _plant_widget_artifacts(self) -> None:
        """The widget's artifacts: one issue under each branch layout, two
        branches no configured repository owns, and two checkouts -- one
        under a branch of its own, one with no branch left at all."""
        for branch in (
            _namespaced_branch(WIDGET_SLUG, BOTH_SIDES_ISSUE_NUMBER),
            _legacy_branch(LEGACY_ISSUE_NUMBER),
            *IGNORED_BRANCHES,
        ):
            self.world.branch(self.clone, branch)
        self.world.checkout(self.widget, BOTH_SIDES_ISSUE_NUMBER)
        self.world.checkout(self.widget, CHECKOUT_ONLY_ISSUE_NUMBER)


if __name__ == "__main__":
    unittest.main()
