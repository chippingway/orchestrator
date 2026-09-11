# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which repository a checkout directory is charged to, and which are charged to nobody.

The claim is driven from the clone identity already read rather than from real
worktrees, because what the rules turn on is the mapping a caller hands over:
which entries answered, what each of them answered, and whether the directory
itself could be read at all. The scan that takes those readings for real is
covered against real checkouts in the inventory's own tests.
"""

from __future__ import annotations

import logging
import unittest
from pathlib import Path

from orchestrator.git.worktrees import checkout_attribution
from tests.git.worktrees.artifact_test_support import (
    COLLIDING_SLUGS,
    GADGET_SLUG,
    LIFECYCLE_LOGGER,
    WIDGET_SLUG,
    _spec,
)

SHARED_CLONE = Path("/tmp/orchestrator-checkout-clone")
OTHER_CLONE = Path("/tmp/orchestrator-checkout-other-clone")

# What a refusal names the directory it will not charge to anybody.
FLAT_SUBJECT = "/tmp/orchestrator-worktrees/issue-9"

FLAT_ISSUE_NUMBER = 9
OTHER_FLAT_ISSUE_NUMBER = 12
# A `REPOS` slug whose sanitized form IS a flat checkout name, which is what
# makes that one path a worktrees root rather than a worktree.
ROOT_SHAPED_SLUG = f"issue-{FLAT_ISSUE_NUMBER}"


class FlatCheckoutClaimTest(unittest.TestCase):
    """`WORKTREES_DIR/issue-<n>` carries no slug, so the clone it is of decides.

    Every configured entry derived that path identically, so the only thing
    that can settle it is the git directory the checkout and a clone share --
    and an entry that did not answer has not been ruled out.
    """

    def test_a_matched_lone_clone_settles_it(self) -> None:
        widget = _spec(WIDGET_SLUG, SHARED_CLONE)
        gadget = _spec(GADGET_SLUG, OTHER_CLONE)

        claim = checkout_attribution._legacy_checkout_claim(
            SHARED_CLONE,
            {widget: SHARED_CLONE, gadget: OTHER_CLONE},
            FLAT_SUBJECT,
        )

        self.assertEqual(claim, checkout_attribution.CheckoutClaim(
            owner=widget, claimants=(widget,),
        ))

    def test_an_unread_repository_clone_claims_it_too(self) -> None:
        # Nothing established that the silent entry is not the one, and
        # dropping it is how a checkout on a shared clone would read as
        # uniquely owned.
        widget = _spec(WIDGET_SLUG, SHARED_CLONE)
        gadget = _spec(GADGET_SLUG, OTHER_CLONE)

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING):
            claim = checkout_attribution._legacy_checkout_claim(
                SHARED_CLONE,
                {widget: SHARED_CLONE, gadget: None},
                FLAT_SUBJECT,
            )

        self.assertEqual(claim, checkout_attribution.CheckoutClaim(
            owner=None, claimants=(widget, gadget),
        ))

    def test_an_unread_checkout_claims_everyone(self) -> None:
        # The directory's own identity is what every other reading is compared
        # against, so a checkout that would not answer leaves every configured
        # entry exactly as plausible as it was.
        widget = _spec(WIDGET_SLUG, SHARED_CLONE)
        gadget = _spec(GADGET_SLUG, OTHER_CLONE)

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING):
            claim = checkout_attribution._legacy_checkout_claim(
                None,
                {widget: SHARED_CLONE, gadget: OTHER_CLONE},
                FLAT_SUBJECT,
            )

        self.assertEqual(claim, checkout_attribution.CheckoutClaim(
            owner=None, claimants=(widget, gadget),
        ))


class UnsettledFlatCheckoutTest(unittest.TestCase):
    """What an operator is told about a flat checkout nobody was charged for.

    Each shape is settled differently by hand -- a store two entries share, a
    repository to go and look at, a directory that is not this orchestrator's
    -- so each has to be recognizable from the line alone.
    """

    def test_several_claimants_are_all_named(self) -> None:
        widget = _spec(WIDGET_SLUG, SHARED_CLONE)
        gadget = _spec(GADGET_SLUG, SHARED_CLONE)

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING) as logs:
            claim = checkout_attribution._legacy_checkout_claim(
                SHARED_CLONE,
                {widget: SHARED_CLONE, gadget: SHARED_CLONE},
                FLAT_SUBJECT,
            )
            refusal = logs.output[0]

        self.assertEqual(claim.claimants, (widget, gadget))
        self.assertIn(WIDGET_SLUG, refusal)
        self.assertIn(GADGET_SLUG, refusal)

    def test_a_lone_unread_claimant_is_named(self) -> None:
        gadget = _spec(GADGET_SLUG, OTHER_CLONE)

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING) as logs:
            claim = checkout_attribution._legacy_checkout_claim(
                SHARED_CLONE, {gadget: None}, FLAT_SUBJECT,
            )
            refusal = logs.output[0]

        self.assertEqual(claim.claimants, (gadget,))
        self.assertIsNone(claim.owner)
        self.assertIn(GADGET_SLUG, refusal)

    def test_a_directory_nobody_claims_stays_quiet(self) -> None:
        # A checkout of a clone no `REPOS` entry names costs nothing and is
        # found on every tick, so it is not an operator's to resolve.
        gadget = _spec(GADGET_SLUG, OTHER_CLONE)

        with self.assertNoLogs(LIFECYCLE_LOGGER, logging.WARNING):
            claim = checkout_attribution._legacy_checkout_claim(
                SHARED_CLONE, {gadget: OTHER_CLONE}, FLAT_SUBJECT,
            )

        self.assertEqual(claim, checkout_attribution.CheckoutClaim(
            owner=None, claimants=(),
        ))


class CountableFlatCheckoutTest(unittest.TestCase):
    """A flat path some entry keeps its checkouts in is not a checkout."""

    def test_a_worktrees_root_is_not_counted(self) -> None:
        # A `REPOS` slug that sanitizes to an `issue-<n>` of its own puts a
        # directory full of checkouts exactly where a flat checkout would be,
        # and the two must not be confused whichever the scan reached first.
        specs = (_spec(ROOT_SHAPED_SLUG, SHARED_CLONE),)

        counted = checkout_attribution._countable_legacy_checkouts(
            specs, frozenset((FLAT_ISSUE_NUMBER, OTHER_FLAT_ISSUE_NUMBER)),
        )

        self.assertEqual(counted, frozenset((OTHER_FLAT_ISSUE_NUMBER,)))


class WorktreeDirectoryTest(unittest.TestCase):
    """Which repositories the path sanitizer hands one checkout directory.

    The clone rules above ask what a directory IS; this one asks the
    configuration, since every repository's checkouts hang off one
    `WORKTREES_DIR` whatever clone it is on.
    """

    def test_a_shared_directory_refuses_both(self) -> None:
        specs = tuple(_spec(slug, SHARED_CLONE) for slug in COLLIDING_SLUGS)

        with self.assertLogs(LIFECYCLE_LOGGER, logging.WARNING) as logs:
            colliding = checkout_attribution._colliding_worktree_slugs(specs)
            refusal = logs.output[0]

        self.assertEqual(colliding, tuple(sorted(COLLIDING_SLUGS)))
        # Both claimants by name: an operator resolving this has to know which
        # two entries were handed the same directory.
        for slug in COLLIDING_SLUGS:
            with self.subTest(slug=slug):
                self.assertIn(slug, refusal)

    def test_distinct_directories_are_kept(self) -> None:
        specs = (
            _spec(WIDGET_SLUG, SHARED_CLONE), _spec(GADGET_SLUG, SHARED_CLONE),
        )

        self.assertEqual(
            checkout_attribution._colliding_worktree_slugs(specs), (),
        )


if __name__ == "__main__":
    unittest.main()
