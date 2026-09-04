# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The finished issue a teardown runs against, and how its host is read back.

Real throughout, for the reason the classification's own fixture is: what a
teardown does IS removing a checkout, so a double of the clone or of the
worktrees under it would hand the fixture's own bookkeeping back instead of
what git was left holding. The bare remote is real for the same reason one
step further out -- the verdicts are taken from the classifier rather than
assembled, and what it asks about a branch it asks the remote.

The verdicts that ARE assembled say so: they are about a teardown pointed at
artifacts nobody attributed to this issue, which is the one shape the
classifier never produces.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from orchestrator.git.worktrees import eligibility, obligations, reclamation
from orchestrator.git.worktrees.models import (
    ArtifactReclamation,
    ArtifactSurface,
    ArtifactVerdict,
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


def _tip(root: Path, revision: str) -> str:
    """The commit one name in this repository stands on, straight from git."""
    return _revision(root, revision)


def _dirty(worktree: Path) -> Path:
    """Leave one file in this checkout that nothing tracks, and name it."""
    loose = worktree / LOOSE_FILE
    loose.write_text(LOOSE_CONTENT)
    return loose


def _ran_git(root: Path, *args: str) -> int:
    """Run one git command that is allowed to fail, and answer with its status.

    What a fixture uses where the point of the call is whether git accepted
    it: a racer's commit the locks are meant to refuse, a worktree lock a
    removal is meant to trip over.
    """
    try:
        return _run_git(*args, cwd=root).returncode
    except subprocess.CalledProcessError as refused:
        return refused.returncode


def _checkout_surface(
    outcome: SurfaceOutcome,
) -> tuple[tuple[ArtifactSurface, SurfaceOutcome], ...]:
    """The whole answer a candidate whose one artifact is a checkout gets.

    The whole of it rather than its first entry, so a case asserting what the
    checkout was left in is also asserting that nothing was reported for a
    surface this candidate does not have.
    """
    return ((ArtifactSurface.WORKTREE, outcome),)


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

    def anchored(self) -> str:
        """The commit this issue's anchor holds, or "" when there is no note."""
        return obligations._anchored_commit(self.spec, ISSUE_NUMBER)
