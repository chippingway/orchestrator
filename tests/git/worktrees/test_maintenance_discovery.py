# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a maintenance pass finds on a host and on the remote beside it.

The local scan already answers for what a host holds; what is pinned down here
is the half it cannot answer -- a branch this clone no longer has a ref for --
and the reading that says which layout an issue was published under.

Driven against real clones, real branches, real checkouts, and real bare
remotes, because both halves of the question are things git answers: the
namespace listing, the ref store the local half is read from, and the exact
names attribution re-derives and compares. A shared clone gets two remotes, so
the one name neither of its repositories can be charged for is refused while
each of them still answers for its own.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git.worktrees import discovery
from orchestrator.git.worktrees.models import CandidateLayout
from tests.git.worktrees.artifact_test_support import (
    GADGET_SLUG,
    WIDGET_SLUG,
    _legacy_branch,
    _namespaced_branch,
    _spec,
)
from tests.git.worktrees.candidate_host_test_support import _branch_at
from tests.git.worktrees.eligibility_test_support import ISSUE_NUMBER
from tests.git.worktrees.maintenance_test_support import (
    LIFECYCLE_LOGGER,
    SIBLING_REMOTE_DIR,
    _MaintenanceTestCase,
)

OTHER_ISSUE_NUMBER = 315
WARNING = "WARNING"


class CandidateLayoutTest(_MaintenanceTestCase):
    """Every shape one issue's artifacts can be found in reads as one candidate."""

    def test_a_checkout_and_branch_read_as_current(self) -> None:
        self.published()
        self.checkout()

        found = self.only_candidate()

        self.assertEqual(found.layout, CandidateLayout.CURRENT)
        self.assertEqual(found.artifacts.branches, (self.branch,))
        self.assertIsNotNone(found.artifacts.worktree)

    def test_the_flat_name_reads_as_the_legacy_layout(self) -> None:
        legacy = _legacy_branch(ISSUE_NUMBER)
        self.published(legacy)

        found = self.only_candidate()

        self.assertEqual(found.layout, CandidateLayout.LEGACY)
        self.assertEqual(found.artifacts.branches, (legacy,))

    def test_both_names_read_as_one_mixed_candidate(self) -> None:
        # A migration leaves an issue carrying both, and no single derivation
        # produces that pair -- so it is one issue with two names rather than
        # two candidates.
        legacy = _legacy_branch(ISSUE_NUMBER)
        self.published()
        self.published(legacy)

        found = self.only_candidate()

        self.assertEqual(found.layout, CandidateLayout.MIXED)
        self.assertEqual(found.artifacts.branches, (self.branch, legacy))

    def test_a_branch_only_out_there_reads_remote(self) -> None:
        # The whole reason this discovery is wider than the scan: the clone was
        # rebuilt, or the ref deleted by hand, and the work is still published.
        self.published()
        _branch_at(self.clone, self.branch, None)

        found = self.only_candidate()

        self.assertEqual(found.layout, CandidateLayout.REMOTE_ONLY)
        self.assertEqual(found.artifacts.branches, (self.branch,))
        self.assertIsNone(found.artifacts.worktree)

    def test_a_checkout_with_no_branch_is_current(self) -> None:
        # Nothing is remote-only while this host still has something to look
        # at, whatever is left of the branch that named it.
        self.published()
        worktree = self.checkout()
        _branch_at(self.clone, self.branch, None)
        self.world.unpublish(self.clone, self.branch)

        found = self.only_candidate()

        self.assertEqual(found.layout, CandidateLayout.CURRENT)
        self.assertEqual(found.artifacts.branches, ())
        self.assertEqual(found.artifacts.worktree, worktree)

    def test_a_local_and_a_remote_name_read_mixed(self) -> None:
        # The two halves are merged into one candidate in the order a teardown
        # takes them, whichever host each name was found on.
        legacy = _legacy_branch(ISSUE_NUMBER)
        self.published()
        self.published(legacy)
        _branch_at(self.clone, legacy, None)

        found = self.only_candidate()

        self.assertEqual(found.layout, CandidateLayout.MIXED)
        self.assertEqual(found.artifacts.branches, (self.branch, legacy))


class CandidateOrderTest(_MaintenanceTestCase):
    """Two discoveries of one unchanged world are the same answer."""

    def test_candidates_are_ordered_by_issue(self) -> None:
        self.published()
        self.published(_namespaced_branch(WIDGET_SLUG, OTHER_ISSUE_NUMBER))
        _branch_at(
            self.clone, _namespaced_branch(WIDGET_SLUG, OTHER_ISSUE_NUMBER),
            None,
        )

        found = self.discovered()

        self.assertEqual(
            tuple(
                candidate.artifacts.issue_number for candidate in found
            ),
            (ISSUE_NUMBER, OTHER_ISSUE_NUMBER),
        )


class SharedCloneDiscoveryTest(_MaintenanceTestCase):
    """A name two repositories could own is charged to neither of them.

    The remote says which repository a branch was pushed to, and that is not
    the question: the local ref of that name is what a teardown goes on to
    delete, and on a shared clone nothing says which entry created it.
    """

    def setUp(self) -> None:
        super().setUp()
        self.sibling = _spec(GADGET_SLUG, self.clone)
        self.world.serve_beside(self.sibling, SIBLING_REMOTE_DIR)
        self.specs = (self.spec, self.sibling)

    def test_a_shared_flat_name_is_nobody_s(self) -> None:
        legacy = _legacy_branch(ISSUE_NUMBER)

        with self.assertLogs(LIFECYCLE_LOGGER, level=WARNING):
            self.published(legacy)
            found = self.discovered(self.specs)

        self.assertEqual(found, ())

    def test_a_shared_flat_name_out_there_is_too(self) -> None:
        legacy = _legacy_branch(ISSUE_NUMBER)
        self.published(legacy)
        _branch_at(self.clone, legacy, None)

        self.assertEqual(self.discovered(self.specs), ())

    def test_each_repository_answers_for_its_own(self) -> None:
        self.published()
        _branch_at(self.clone, self.branch, None)

        found = self.only_candidate(self.specs)

        self.assertEqual(found.artifacts.spec.slug, WIDGET_SLUG)
        self.assertEqual(found.layout, CandidateLayout.REMOTE_ONLY)

    def test_a_sibling_s_name_here_is_not_ours(self) -> None:
        # A branch spelled for the other entry that turned up on this remote is
        # evidence about neither: this repository never published it, and the
        # other one never published it HERE.
        sibling_branch = _namespaced_branch(GADGET_SLUG, ISSUE_NUMBER)
        self.published(sibling_branch)
        _branch_at(self.clone, sibling_branch, None)

        found = self.discovered((self.spec,))

        self.assertEqual(found, ())


class UnreachableRemoteTest(_MaintenanceTestCase):
    """A repository whose remote will not answer is left out entirely."""

    def test_an_unreachable_remote_refuses_it_all(self) -> None:
        # Every question a pass asks after this one goes to the same remote, so
        # reporting the local half alone would hand out a picture of a host
        # that nothing could act on.
        self.published()
        self.checkout()
        self.world.unreachable(self.spec)

        with self.assertLogs(LIFECYCLE_LOGGER, level=WARNING):
            scanned = discovery._maintenance_candidates((self.spec,))

        self.assertEqual(scanned.candidates, ())
        self.assertEqual(scanned.refused, (WIDGET_SLUG,))

    def test_a_transport_that_raises_only_refuses(self) -> None:
        # The transport answers None for what it recognizes and raises for what
        # is underneath it; an exception out of one repository's listing would
        # otherwise take every other repository in the discovery with it.
        self.published()

        with (
            patch.object(
                discovery.ref_transport,
                "_remote_ref_names",
                side_effect=OSError("git could not be spawned"),
            ),
            self.assertLogs(LIFECYCLE_LOGGER, level=WARNING),
        ):
            scanned = discovery._maintenance_candidates((self.spec,))

        self.assertEqual(scanned.candidates, ())
        self.assertEqual(scanned.refused, (WIDGET_SLUG,))

    def test_an_empty_remote_is_not_a_refusal(self) -> None:
        # The empty listing is an answer: this repository has published
        # nothing that is still out there, and what the host holds is reported
        # exactly as it stands.
        self.world.commit_on(self.clone, self.branch)
        worktree = self.checkout()

        scanned = discovery._maintenance_candidates((self.spec,))

        self.assertEqual(scanned.refused, ())
        self.assertEqual(len(scanned.candidates), 1)
        self.assertEqual(scanned.candidates[0].artifacts.worktree, worktree)
        self.assertEqual(
            scanned.candidates[0].artifacts.branches, (self.branch,),
        )


if __name__ == "__main__":
    unittest.main()
