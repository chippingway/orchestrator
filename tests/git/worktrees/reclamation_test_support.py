# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The finished issue a teardown runs against, and how its host is read back.

Real throughout, for the reason the classification's own fixture is: what a
teardown does IS removing a checkout, deleting a ref, and pushing a deletion
to a remote, so a double of any of them would hand the fixture's own
bookkeeping back instead of what git and the remote were left holding. The
bare repository matters most -- a branch reclaimed on the remote and a branch
merely dropped from a tracking ref look identical to everything except the
remote itself.

The verdicts are taken from the classifier rather than assembled, so what a
case spends is what that pass really hands over. The two that ARE assembled
say so: they are about a teardown pointed at artifacts nobody attributed to
this issue, which is the one shape the classifier never produces.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from orchestrator import config
from orchestrator.git.worktrees import eligibility, evidence, reclamation
from orchestrator.git.worktrees.models import (
    ArtifactReclamation,
    ArtifactSurface,
    ArtifactVerdict,
    ProbeAnswer,
    SurfaceOutcome,
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
    _revision,
)
from tests.git.worktrees.eligibility_test_support import (
    ISSUE_NUMBER,
    _candidate,
    _github,
)
from tests.workflow.stages.question.question_real_git_test_support import (
    _run_git,
)

LOOSE_FILE = "left-behind.txt"
LOOSE_CONTENT = "an agent's unfinished work\n"
# An issue whose artifacts sit beside this one's on the same clone, for the
# cases about a teardown pointed at a name that is not its own.
OTHER_ISSUE_NUMBER = 315


def _holds(spec: config.RepoSpec, branch: str) -> bool:
    """Whether this clone still carries `branch`."""
    tip = evidence._local_branch_tip(spec, branch)
    return tip.answer is ProbeAnswer.CONFIRMED


def _publishes(spec: config.RepoSpec, branch: str) -> bool:
    """Whether the remote still carries `branch`, asked of the remote."""
    return evidence._published_tip(spec, branch).answer is ProbeAnswer.CONFIRMED


def _tip(clone: Path, branch: str) -> str:
    """The commit this clone has `branch` on, read straight from git."""
    return _revision(clone, branch)


def _lock_checkout(clone: Path, worktree: Path) -> None:
    """Lock one worktree, which is a removal git refuses without `--force`."""
    _run_git("worktree", "lock", str(worktree), cwd=clone)


def _surfaces(
    checkout: SurfaceOutcome | None,
    remote: SurfaceOutcome,
    local: SurfaceOutcome,
) -> tuple[tuple[ArtifactSurface, SurfaceOutcome], ...]:
    """The surfaces of one candidate, in the order a teardown takes them.

    The checkout is left out rather than reported when a case has none, which
    is the shape a branch-only candidate answers in.
    """
    reported = (
        (ArtifactSurface.REMOTE_BRANCH, remote),
        (ArtifactSurface.LOCAL_BRANCH, local),
    )
    if checkout is None:
        return reported
    return ((ArtifactSurface.WORKTREE, checkout), *reported)


class _ReclaimTestCase(unittest.TestCase):
    """One finished issue, its artifacts, and the teardown spent on them."""

    def setUp(self) -> None:
        self.world = _CandidateWorld()
        self.world.prepare(self)
        self.clone = self.world.clone(CLONE_NAME)
        self.spec = _spec(WIDGET_SLUG, self.clone)
        self.world.serve(self.spec)
        self.branch = _namespaced_branch(WIDGET_SLUG, ISSUE_NUMBER)
        self.branches = (self.branch,)
        self.gh = _github()

    def published(self, branch: str | None = None) -> str:
        """One commit on this issue's branch, pushed, and merged into base.

        The whole of what a finished issue leaves behind: a branch the remote
        carries at the same commit this host does, and a base that already
        holds that commit -- the one shape every surface of a candidate is
        cleared in.
        """
        branch = branch or self.branch
        tip = self.world.commit_on(self.clone, branch)
        self.world.publish(self.clone, branch, branch)
        self.world.publish(self.clone, BASE_BRANCH, branch)
        return tip

    def checkout(self, issue_number: int = ISSUE_NUMBER) -> Path:
        """One issue's worktree, on the branch its creator leaves it on."""
        return self.world.attached_checkout(
            self.spec,
            issue_number,
            _namespaced_branch(WIDGET_SLUG, issue_number),
        )

    def verdict(self, **artifacts) -> ArtifactVerdict:
        """The classification of this issue's candidate, in the shape given."""
        if not artifacts:
            artifacts = {"branches": self.branches}
        return eligibility._classify_artifacts(
            self.gh, _candidate(self.spec, ISSUE_NUMBER, **artifacts),
        )

    def spend(self, verdict: ArtifactVerdict) -> ArtifactReclamation:
        """Run the teardown one already-taken verdict entitles."""
        return reclamation._reclaim_artifacts(verdict)

    def outcomes(
        self, reclaimed: ArtifactReclamation,
    ) -> tuple[tuple[ArtifactSurface, SurfaceOutcome], ...]:
        """Each surface and what it was left in, subjects aside."""
        return tuple(
            (taken.surface, taken.outcome) for taken in reclaimed.surfaces
        )

    def standing(
        self, worktree: Path | None = None,
    ) -> tuple[bool, bool, bool]:
        """What is still there: the checkout, the branch, the remote's copy."""
        return (
            worktree is not None and worktree.exists(),
            _holds(self.spec, self.branch),
            _publishes(self.spec, self.branch),
        )
