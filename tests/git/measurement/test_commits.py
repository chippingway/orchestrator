# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Freezing the base and proving the candidate against real repositories.

Both ends of a measurement are pinned here for the same reason: what makes
either of them worth anything is that a later tick, a retry after a crash, and
a human reading the diff all get the same two commits. So the base is checked
against a remote that moves and a local ref that lies, and the candidate
against ids this repository does and does not hold.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git import authentication
from orchestrator.git.measurement import commits
from orchestrator.git.measurement.models import MeasurementFailure
from tests.git.measurement import measurement_test_support as _support

_REMOTE_TIP_READ = "_remote_branch_tip"
_FEATURE_PATH = "feature.py"
_TAG_NAME = "v1"


class BaseFreezeTest(unittest.TestCase):
    """The frozen base is the remote's answer, proven present in this store."""

    def setUp(self) -> None:
        self._repo = _support.CandidateRepo()
        self._repo.prepare(self)

    def test_the_remote_tip_is_what_is_frozen(self) -> None:
        frozen = commits._freeze_base_commit(
            self._repo.spec, self._repo.worktree,
        )

        self.assertTrue(frozen.is_frozen)
        self.assertEqual(frozen.sha, self._repo.base())

    def test_a_repointed_local_ref_decides_nothing(self) -> None:
        # `refs/remotes/origin/main` lives in the store the agent's worktree
        # shares. Pointed at the candidate, a base-relative diff would measure
        # the agent's work against itself and report a candidate of no size.
        remote_tip = self._repo.base()
        candidate = self._repo.commit({_FEATURE_PATH: "one\ntwo\n"})
        _support.point_local_base_at(self._repo, candidate)

        frozen = commits._freeze_base_commit(
            self._repo.spec, self._repo.worktree,
        )

        self.assertEqual(frozen.sha, remote_tip)

    def test_a_base_this_clone_lacks_is_fetched(self) -> None:
        # The base advances between the tick's fetch and the measurement, so
        # the tip the remote names is routinely an object this clone has not
        # seen. One fetch is what turns that into a base a diff can be taken
        # against, rather than a failure nobody had to take.
        advanced = self._repo.advance_base_from_elsewhere()

        frozen = commits._freeze_base_commit(
            self._repo.spec, self._repo.worktree,
        )

        self.assertEqual(frozen.sha, advanced)

    def test_a_base_still_missing_is_typed(self) -> None:
        # The remote rewrote the branch, or the fetch brought nothing: either
        # way no diff can be taken, and a candidate with no diff is unmeasured
        # rather than small.
        with patch.object(
            authentication, _REMOTE_TIP_READ, return_value=_support.ABSENT_SHA,
        ):
            frozen = commits._freeze_base_commit(
                self._repo.spec, self._repo.worktree,
            )

        self.assertEqual(frozen.failure, MeasurementFailure.BASE_ABSENT)
        self.assertFalse(frozen.is_frozen)

    def test_a_missing_base_keeps_the_id_it_learned(self) -> None:
        # The remote NAMED it, so the id is the only record of which commit
        # this attempt was about -- and the only thing a retry can ask for. A
        # failure recorded without it leaves the next pass re-reading a remote
        # whose base has moved on, measuring a different pair. Nothing may
        # measure against it either way, which `is_frozen` above refuses.
        with patch.object(
            authentication, _REMOTE_TIP_READ, return_value=_support.ABSENT_SHA,
        ):
            frozen = commits._freeze_base_commit(
                self._repo.spec, self._repo.worktree,
            )

        self.assertEqual(frozen.sha, _support.ABSENT_SHA)

    def test_an_unanswered_remote_is_typed(self) -> None:
        # None is the read having failed -- no token, hijackable transport
        # config, an unreachable host -- and "" is the remote saying it does
        # not carry the branch. Neither establishes a commit.
        for answer in (None, ""):
            with self.subTest(answer=answer):
                with patch.object(
                    authentication, _REMOTE_TIP_READ, return_value=answer,
                ):
                    frozen = commits._freeze_base_commit(
                        self._repo.spec, self._repo.worktree,
                    )

                self.assertEqual(
                    frozen.failure, MeasurementFailure.BASE_UNREADABLE,
                )
                self.assertFalse(frozen.is_frozen)


class CandidateProofTest(unittest.TestCase):
    """A candidate is the exact id git resolved, and one this host holds."""

    def setUp(self) -> None:
        self._repo = _support.CandidateRepo()
        self._repo.prepare(self)

    def test_the_named_revision_is_resolved(self) -> None:
        # Named rather than left as HEAD: the branch moves, and a measurement
        # recorded against "whatever HEAD was" is one no retry can repeat.
        first = self._repo.commit({_FEATURE_PATH: "one\n"})
        latest = self._repo.commit({_FEATURE_PATH: "one\ntwo\n"})

        for revision, expected in (
            (first, first), (_support.CANDIDATE_BRANCH, latest),
        ):
            with self.subTest(revision=revision):
                proven = commits._prove_candidate_commit(
                    self._repo.worktree, revision,
                )
                self.assertTrue(proven.is_frozen)
                self.assertEqual(proven.sha, expected)

    def test_an_annotated_tag_peels_to_its_commit(self) -> None:
        # An annotated tag is an object of its own that points at the commit,
        # so a revision naming one resolves to the TAG's id. Recorded, that id
        # is evidence about a label rather than about the work: nothing
        # downstream could compare it to a branch tip, and the tag can be moved
        # or deleted while the commit cannot.
        candidate = self._repo.commit({_FEATURE_PATH: "one\n"})
        _support.run_git(
            "tag", "-a", _TAG_NAME, "-m", "release",
            cwd=self._repo.worktree, env_extra=_support.AUTHOR_ENV,
        )
        tag_object = _support.run_git(
            "rev-parse", "--verify", _TAG_NAME, cwd=self._repo.worktree,
        ).strip()

        proven = commits._prove_candidate_commit(
            self._repo.worktree, _TAG_NAME,
        )

        self.assertNotEqual(tag_object, candidate)
        self.assertEqual(proven.sha, candidate)

    def test_an_object_this_host_lacks_is_typed(self) -> None:
        # git resolves a full object id to itself without consulting the
        # store, so a candidate recorded on another host reads back looking
        # exactly like one that is here -- and the diff that spends it reports
        # no lines, which is what a candidate adding nothing reports too.
        proven = commits._prove_candidate_commit(
            self._repo.worktree, _support.ABSENT_SHA,
        )

        self.assertEqual(proven.failure, MeasurementFailure.CANDIDATE_ABSENT)
        self.assertFalse(proven.is_frozen)

    def test_an_absent_object_keeps_its_identity(self) -> None:
        # The id it resolved to is the only record of which commit the attempt
        # was about. Dropped, a retry has nothing to ask for and proves
        # whatever the checkout points at by then instead.
        proven = commits._prove_candidate_commit(
            self._repo.worktree, _support.ABSENT_SHA,
        )

        self.assertEqual(proven.sha, _support.ABSENT_SHA)

    def test_an_unresolvable_revision_is_typed(self) -> None:
        # Nothing was named, so nothing comes back named: a revision that will
        # not resolve is a checkout that cannot say what it is on.
        proven = commits._prove_candidate_commit(
            self._repo.worktree, "no-such-branch",
        )

        self.assertEqual(
            proven.failure, MeasurementFailure.CANDIDATE_UNREADABLE,
        )
        self.assertEqual(proven.sha, "")


if __name__ == "__main__":
    unittest.main()
