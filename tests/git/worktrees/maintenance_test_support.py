# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The finished issue a maintenance pass runs over, on a real host and remote.

The world is the artifact classification's own -- a clone, the bare repository
its authenticated transport is pointed at, and the checkouts under a redirected
worktrees root -- because a pass is only worth testing against the things it
actually mutates: `worktree remove` refusing a tree it has been written in, a
leased delete the remote turns down, a ref store that will not let go of a
branch that has moved. A double of any of them would hand the fixture's own
answer back.

What is doubled is the issue and its pull requests, through the in-memory
client, since the ending a candidate needs is a fact about GitHub rather than
about the host.

The quiet period is real too, which is why every case that expects a pass to
act back-dates the checkout first: a tree created moments ago is one this pass
is designed to leave alone, and a fixture that patched the constant away would
stop testing the guard that says so.
"""

from __future__ import annotations

import os
import time
import unittest
from collections.abc import Sequence
from pathlib import Path

from orchestrator import config
from orchestrator.git.worktrees import discovery, maintenance, probes
from orchestrator.git.worktrees.models import (
    MaintenanceCandidate,
    MaintenanceResult,
)
from tests.git.worktrees.artifact_test_support import (
    BASE_BRANCH,
    WIDGET_SLUG,
    _namespaced_branch,
    _spec,
)
from tests.git.worktrees.candidate_host_test_support import (
    CLONE_NAME,
    _CandidateWorld,
)
from tests.git.worktrees.eligibility_test_support import ISSUE_NUMBER, _github

# Far enough back that the pass's own quiet period has passed for a checkout,
# derived from that period rather than written out so the two cannot drift.
SETTLED_SECONDS = 2 * maintenance._QUIET_PERIOD_SECONDS

# The second bare repository a shared-clone case serves, named apart from the
# world's own so both can stand at once.
SIBLING_REMOTE_DIR = "sibling.git"

LIFECYCLE_LOGGER = "orchestrator.worktree_lifecycle"


def _never_claimed(_repo_slug: str, _issue_number: int) -> bool:
    """The guard a host with nothing running for this issue answers with."""
    return False


def _always_claimed(_repo_slug: str, _issue_number: int) -> bool:
    """The guard a host that is mid-run for this issue answers with."""
    return True


def _unanswerable_claim(_repo_slug: str, _issue_number: int) -> bool:
    """A guard that fails the way one reaching into a live scheduler can."""
    raise RuntimeError("the scheduler could not be asked")


def _settle(worktree: Path) -> None:
    """Back-date a checkout to before the pass's quiet period."""
    settled = time.time() - SETTLED_SECONDS
    os.utime(worktree, (settled, settled))


def _refused_delete(*_args, **_options) -> bool:
    """A teardown step the host or the remote turned down."""
    return False


class _MaintenanceTestCase(unittest.TestCase):
    """One finished issue, with its artifacts on a real host and remote."""

    def setUp(self) -> None:
        self.world = _CandidateWorld()
        self.world.prepare(self)
        self.clone = self.world.clone(CLONE_NAME)
        self.spec = _spec(WIDGET_SLUG, self.clone)
        self.world.serve(self.spec)
        self.branch = _namespaced_branch(WIDGET_SLUG, ISSUE_NUMBER)
        self.gh = _github()

    def published(self, branch: str | None = None) -> str:
        """Put one commit on a branch and push it, as a run's own round does."""
        branch = branch or self.branch
        return self.world.publish(
            self.clone, branch, self.world.commit_on(self.clone, branch),
        )

    def landed(self, branch: str | None = None) -> str:
        """Publish that branch and move the remote's base onto it.

        The ordinary shape of a merged pull request, and the cheapest way to a
        candidate the classification clears: the tip the artifacts stand on is
        one the base already carries, so nothing is lost by deleting them.
        """
        branch = branch or self.branch
        tip = self.published(branch)
        self.world.publish(self.clone, BASE_BRANCH, branch)
        return tip

    def checkout(self, branch: str | None = None) -> Path:
        """Add this issue's worktree, on the branch its creator leaves it on."""
        return self.world.attached_checkout(
            self.spec, ISSUE_NUMBER, branch or self.branch,
        )

    def settled_checkout(self, branch: str | None = None) -> Path:
        """The same checkout, left alone long enough for the pass to act."""
        worktree = self.checkout(branch)
        _settle(worktree)
        return worktree

    @property
    def only_branch(self) -> tuple[str, ...]:
        """This issue's one branch, as a listing of what a host still holds."""
        return (self.branch,)

    def discovered(
        self, specs: Sequence[config.RepoSpec] | None = None,
    ) -> tuple[MaintenanceCandidate, ...]:
        """Every candidate the discovery finds on this host and its remote."""
        return discovery._maintenance_candidates(
            specs or (self.spec,),
        ).candidates

    def only_candidate(self, specs=None) -> MaintenanceCandidate:
        """The single candidate this host and its remote hold between them."""
        found = self.discovered(specs)
        self.assertEqual(len(found), 1, f"expected one candidate, got {found}")
        return found[0]

    def swept(
        self,
        candidates: Sequence[MaintenanceCandidate] | None = None,
        *,
        claimed=_never_claimed,
    ) -> tuple[MaintenanceResult, ...]:
        """Run one maintenance pass over what the discovery found."""
        return maintenance._maintained_candidates(
            self.gh,
            self.discovered() if candidates is None else candidates,
            claimed=claimed,
        )

    def only_result(self, **options) -> MaintenanceResult:
        """The single answer a pass over this host's one candidate gives."""
        swept = self.swept(**options)
        self.assertEqual(len(swept), 1, f"expected one candidate, got {swept}")
        return swept[0]

    def local_branches(self) -> tuple[str, ...]:
        """Every orchestrator-owned branch the clone still carries."""
        return probes._local_orchestrator_branches(self.clone) or ()

    def remote_branches(self) -> tuple[str, ...]:
        """Every orchestrator-owned branch the remote still carries."""
        return discovery._remote_orchestrator_branches(self.spec) or ()
