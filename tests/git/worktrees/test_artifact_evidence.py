# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The five reads a terminal artifact is judged by, one answer at a time.

Driven against real clones, real checkouts, real refs, and a real bare remote,
because the third answer is the whole point of these probes and it only exists
against a real host: a stubbed `rev-parse` returns whatever the stub was told
to, while a repository that is not there, a ref that is not there, and a ref
that is there are three different exit statuses git assigns on its own.

The remote is real for a second reason. What separates `_published_tip` from
the local ref that resembles it is that one of them can be written by an agent
and the other cannot, and only a fixture holding both can show the two
disagreeing.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git import branch_transport, commands
from orchestrator.git.worktrees import evidence
from orchestrator.git.worktrees.models import BranchTip, ProbeAnswer
from tests.git.worktrees.artifact_test_support import (
    BASE_BRANCH,
    WIDGET_SLUG,
    _namespaced_branch,
    _spec,
)
from tests.git.worktrees.candidate_host_test_support import (
    CLONE_NAME,
    _branch_at,
    _CandidateWorld,
    _foreign_checkout,
    _revision,
    _tracking_ref,
)
from tests.git.worktrees.eligibility_test_support import ISSUE_NUMBER

ANOTHER_BRANCH = "orchestrator/acme__widget/issue-99"
LOOSE_FILE = "left-behind.txt"
LOOSE_CONTENT = "an agent's unfinished work\n"
MISSING_REVISION = "0000000000000000000000000000000000000000"
NOT_A_CLONE = "no-repository-here"
NOTHING_AT_ALL = "never-created"
LOOPING_LINK = "looping"
LOOPING_BACK = "looping-back"


def _named(sha: str) -> BranchTip:
    """One commit as the remote naming it, which is how a base arrives."""
    return BranchTip(answer=ProbeAnswer.CONFIRMED, sha=sha)


class _HostTestCase(unittest.TestCase):
    """A clone, its issue branch name, and the spec naming both."""

    def setUp(self) -> None:
        self.world = _CandidateWorld()
        self.world.prepare(self)
        self.clone = self.world.clone(CLONE_NAME)
        self.spec = _spec(WIDGET_SLUG, self.clone)
        self.branch = _namespaced_branch(WIDGET_SLUG, ISSUE_NUMBER)

    def commit(self) -> str:
        """Put one commit on this issue's branch."""
        return self.world.commit_on(self.clone, self.branch)


class CheckoutIdentityTest(_HostTestCase):
    """Whether the directory at the issue's path is the issue's checkout."""

    def test_its_own_branch_confirms(self) -> None:
        _branch_at(self.clone, self.branch, BASE_BRANCH)
        worktree = self.world.attached_checkout(
            self.spec, ISSUE_NUMBER, self.branch,
        )

        identified = evidence._checkout_identity(
            self.spec, ISSUE_NUMBER, worktree,
        )

        self.assertIs(identified, ProbeAnswer.CONFIRMED)

    def test_a_repository_of_its_own_is_refuted(self) -> None:
        # The path is the one the creators would use and the directory is a
        # git repository, so every reading short of the shared object store
        # says this is the issue's checkout -- and reclaiming it would take a
        # repository this orchestrator never made.
        worktree = _foreign_checkout(self.spec, ISSUE_NUMBER)

        identified = evidence._checkout_identity(
            self.spec, ISSUE_NUMBER, worktree,
        )

        self.assertIs(identified, ProbeAnswer.REFUTED)

    def test_another_branch_and_a_detachment_refute(self) -> None:
        # Both are a checkout of this clone that is not on this issue's work:
        # the first is somebody else's branch parked in our directory, the
        # second is commits sitting on no branch at all.
        _branch_at(self.clone, ANOTHER_BRANCH, BASE_BRANCH)
        elsewhere = self.world.attached_checkout(
            self.spec, ISSUE_NUMBER, ANOTHER_BRANCH,
        )
        detached = self.world.checkout(self.spec, ISSUE_NUMBER + 1)

        for worktree, issue_number in (
            (elsewhere, ISSUE_NUMBER), (detached, ISSUE_NUMBER + 1),
        ):
            with self.subTest(worktree=worktree.name):
                self.assertIs(
                    evidence._checkout_identity(
                        self.spec, issue_number, worktree,
                    ),
                    ProbeAnswer.REFUTED,
                )

    def test_no_repository_at_all_is_unreadable(self) -> None:
        # Nothing was established about the directory, which is not the same
        # answer as establishing that it is somebody else's.
        worktree = self.world.path(NOT_A_CLONE)
        worktree.mkdir()

        identified = evidence._checkout_identity(
            self.spec, ISSUE_NUMBER, worktree,
        )

        self.assertIs(identified, ProbeAnswer.UNREADABLE)


class WorktreeCleanlinessTest(_HostTestCase):
    """Whether a checkout PROVED it is carrying nothing loose."""

    def setUp(self) -> None:
        super().setUp()
        _branch_at(self.clone, self.branch, BASE_BRANCH)
        self.worktree = self.world.attached_checkout(
            self.spec, ISSUE_NUMBER, self.branch,
        )

    def test_a_fresh_checkout_is_confirmed(self) -> None:
        self.assertIs(
            evidence._clean_worktree(self.worktree), ProbeAnswer.CONFIRMED,
        )

    def test_an_untracked_file_refutes(self) -> None:
        (self.worktree / LOOSE_FILE).write_text(LOOSE_CONTENT)

        self.assertIs(
            evidence._clean_worktree(self.worktree), ProbeAnswer.REFUTED,
        )

    def test_a_tree_that_will_not_report_is_unread(self) -> None:
        # A status that could not be taken names no paths, which is what an
        # empty tree names too -- so the answer has to come from whether the
        # read happened rather than from what it listed. A directory that is
        # no repository and a directory that is not there at all are both
        # that, and the second fails the spawn rather than the command.
        no_repository = self.world.path(NOT_A_CLONE)
        no_repository.mkdir()
        for tree in (no_repository, self.world.path(NOTHING_AT_ALL)):
            with self.subTest(tree=tree.name):
                self.assertIs(
                    evidence._clean_worktree(tree), ProbeAnswer.UNREADABLE,
                )


    def test_a_tree_that_will_not_resolve_is_unread(self) -> None:
        # The read names the tree it reports on, and naming it resolves the
        # path -- which on Python 3.12 raises out of `Path.resolve` for a
        # symlink loop rather than answering. A checkout is a tree an agent
        # owns and can rearrange into one, so the probe answers instead of
        # ending the pass that asked.
        looping = self.world.path(LOOPING_LINK)
        back = self.world.path(LOOPING_BACK)
        looping.symlink_to(back)
        back.symlink_to(looping)

        self.assertIs(
            evidence._clean_worktree(looping), ProbeAnswer.UNREADABLE,
        )


class BranchTipTest(_HostTestCase):
    """What a local branch stands on, and the two ways it does not answer."""

    def test_a_branch_resolves_to_its_commit(self) -> None:
        tip = self.commit()

        resolved = evidence._local_branch_tip(self.spec, self.branch)

        self.assertIs(resolved.answer, ProbeAnswer.CONFIRMED)
        self.assertEqual(resolved.sha, tip)

    def test_an_absent_branch_is_refuted(self) -> None:
        resolved = evidence._local_branch_tip(self.spec, self.branch)

        self.assertIs(resolved.answer, ProbeAnswer.REFUTED)
        self.assertEqual(resolved.sha, "")

    def test_a_clone_that_will_not_open_is_unread(self) -> None:
        # git's own no is exit 1 and everything else is a reading that never
        # established anything -- a caller that only tested for a non-zero
        # exit would delete a branch on the strength of an unopenable clone.
        elsewhere = self.world.path(NOT_A_CLONE)
        elsewhere.mkdir()

        resolved = evidence._local_branch_tip(
            _spec(WIDGET_SLUG, elsewhere), self.branch,
        )

        self.assertIs(resolved.answer, ProbeAnswer.UNREADABLE)

    def test_a_git_that_cannot_be_spawned_is_unread(self) -> None:
        with patch.object(
            commands, "_git_hardened", side_effect=OSError("no git here"),
        ):
            resolved = evidence._local_branch_tip(self.spec, self.branch)

        self.assertIs(resolved.answer, ProbeAnswer.UNREADABLE)


class PublishedTipTest(_HostTestCase):
    """What the remote itself says a branch is at."""

    def test_a_pushed_branch_resolves(self) -> None:
        self.world.serve(self.spec)
        tip = self.commit()
        self.world.publish(self.clone, self.branch, self.branch)

        published = evidence._published_tip(self.spec, self.branch)

        self.assertIs(published.answer, ProbeAnswer.CONFIRMED)
        self.assertEqual(published.sha, tip)

    def test_a_branch_the_remote_lacks_is_refuted(self) -> None:
        # The ordinary terminal shape rather than a failure: a merged pull
        # request's head branch is deleted there.
        self.world.serve(self.spec)
        self.commit()

        published = evidence._published_tip(self.spec, self.branch)

        self.assertIs(published.answer, ProbeAnswer.REFUTED)
        self.assertEqual(published.sha, "")

    def test_a_tracking_ref_answers_for_nothing(self) -> None:
        # The tampering this probe exists for. The tracking ref is a local ref
        # in the object store the per-issue worktrees share, so an agent can
        # point it at its own commit -- and the remote goes on saying what it
        # actually holds.
        self.world.serve(self.spec)
        planted = self.commit()
        _tracking_ref(self.clone, self.branch, planted)

        published = evidence._published_tip(self.spec, self.branch)

        self.assertIs(published.answer, ProbeAnswer.REFUTED)

    def test_a_transport_that_raised_is_unread(self) -> None:
        # The transport answers `None` for the failures it recognizes and
        # raises for the ones underneath them -- no git to spawn, a clone
        # removed since the scan named it. A probe whose contract is three
        # answers must not have a fourth, so both arrive as the same one.
        self.world.serve(self.spec)
        self.commit()

        with patch.object(
            branch_transport,
            "_remote_branch_tip",
            side_effect=OSError("no git here"),
        ):
            published = evidence._published_tip(self.spec, self.branch)

        self.assertIs(published.answer, ProbeAnswer.UNREADABLE)

    def test_an_unreachable_remote_is_unread(self) -> None:
        # Neither the branch being there nor its absence was established, and
        # a caller that read this as "the remote does not have it" would go on
        # to decide the branch on evidence nobody produced.
        self.world.unreachable(self.spec)
        self.commit()

        published = evidence._published_tip(self.spec, self.branch)

        self.assertIs(published.answer, ProbeAnswer.UNREADABLE)


class BaseAncestryTest(_HostTestCase):
    """Whether a base commit the caller established carries a branch tip."""

    def test_a_tip_the_base_holds_is_confirmed(self) -> None:
        # The merged shape: the base has moved onto a commit that descends
        # from what the branch is standing on.
        tip = self.commit()
        merged = self.world.commit_on(
            self.clone, BASE_BRANCH, start=self.branch,
        )

        self.assertIs(
            evidence._base_contains(self.spec, _named(merged), tip),
            ProbeAnswer.CONFIRMED,
        )

    def test_a_tip_ahead_of_the_base_is_refuted(self) -> None:
        # Both ends are things the caller established, so what the clone's own
        # `refs/remotes/...` say about either is not consulted at all.
        base = _named(_revision(self.clone, BASE_BRANCH))
        tip = self.commit()

        self.assertIs(
            evidence._base_contains(self.spec, base, tip),
            ProbeAnswer.REFUTED,
        )

    def test_a_commit_this_clone_lacks_is_unread(self) -> None:
        tip = self.commit()

        self.assertIs(
            evidence._base_contains(self.spec, _named(MISSING_REVISION), tip),
            ProbeAnswer.UNREADABLE,
        )

    def test_a_base_nobody_named_is_unread(self) -> None:
        # The remote would not say what the base is on, so there is nothing to
        # measure against -- which is decided here rather than by each caller,
        # so none of them can reach the comparison holding a base nobody
        # named.
        tip = self.commit()

        for unnamed in (ProbeAnswer.REFUTED, ProbeAnswer.UNREADABLE):
            with self.subTest(base=unnamed):
                self.assertIs(
                    evidence._base_contains(
                        self.spec, BranchTip(answer=unnamed), tip,
                    ),
                    ProbeAnswer.UNREADABLE,
                )


if __name__ == "__main__":
    unittest.main()
