# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Subject-shape predicates, commit-subject reads, and ahead/behind counts."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git import commands
from orchestrator.git.publication import probes

from tests.git.publication.publication_helpers import (
    DEFAULT_REVISION_RANGE,
    GIT_HELPER,
    HARDENED_HELPER,
    WORKTREE,
    _GitRecorder,
    _spec,
)

BRANCH = "orchestrator/issue-5"
NO_DIVERGENCE = (0, 0)


class ConventionalSubjectHelperTest(unittest.TestCase):
    """Direct coverage for the regex helper, since the convention list grew
    beyond what the prompts spell out."""

    def test_accepts_basic_types(self) -> None:
        for subject in (
            "feat: add thing",
            "fix: bug",
            "chore: bump dep",
            "docs: tweak",
            "refactor: rename foo",
            "test: cover edge case",
            "perf: speed it up",
            "ci: fix workflow",
        ):
            self.assertTrue(
                probes._is_conventional_subject(subject),
                f"expected conventional: {subject!r}",
            )

    def test_accepts_scope_and_breaking(self) -> None:
        self.assertTrue(probes._is_conventional_subject("feat(api): foo"))
        self.assertTrue(probes._is_conventional_subject("fix!: bar"))
        self.assertTrue(probes._is_conventional_subject("feat(api)!: baz"))

    def test_rejects_non_conventional(self) -> None:
        for subject in (
            "",
            "Add a thing",
            "wip: thing",
            "feat:",  # no subject after colon
            "feat:   ",  # whitespace-only subject
            "Feat: cap type",  # types must be lowercase
            "  feat: leading",  # leading whitespace not accepted
        ):
            self.assertFalse(
                probes._is_conventional_subject(subject),
                f"expected non-conventional: {subject!r}",
            )


class PrefixedSubjectHelperTest(unittest.TestCase):
    """`_is_prefixed_subject` is broader than `_is_conventional_subject`: it
    accepts any lowercase `<token>: <subject>` prefix, so repo-local styles
    survive, while still rejecting prose and bare prefixes."""

    def test_accepts_conventional_and_local_prefixes(self) -> None:
        for subject in (
            "feat: add thing",
            "fix(api)!: drop endpoint",
            "event: add the gala",  # not a Conventional type
            "career: open a role",
            "ui: tweak the spacing",
        ):
            self.assertTrue(
                probes._is_prefixed_subject(subject),
                f"expected prefixed: {subject!r}",
            )

    def test_rejects_prose_and_bare_prefixes(self) -> None:
        for subject in (
            "",
            "updated stuff",  # no colon
            "fixed it",  # no colon
            "Add a thing",  # not prefixed
            "Note: capitalized token",  # token must start lowercase
            "event:",  # no subject after colon
            "event:   ",  # whitespace-only subject
            "  event: leading",  # leading whitespace not accepted
        ):
            self.assertFalse(
                probes._is_prefixed_subject(subject),
                f"expected non-prefixed: {subject!r}",
            )


class FirstCommitSubjectBaseBranchTest(unittest.TestCase):
    """`_first_commit_subject` must compare against `spec.base_branch`, not
    the global `config.BASE_BRANCH`. With `REPOS=...|...|master` and the
    legacy `BASE_BRANCH=main`, the global default would point at the wrong
    remote and either fail or include unrelated commits."""

    def test_uses_per_spec_base_branch(self) -> None:
        git = _GitRecorder("feat: hello\n")
        subject = self._read_subject(git, _spec(base_branch="master"))
        self.assertEqual(subject, "feat: hello")
        self.assertEqual(len(git.calls), 1)
        args, _cwd = git.calls[0]
        # The third positional arg to `_git` is the rev range; it must
        # reference master (the spec's base_branch), not the cached `main`.
        self.assertIn("origin/master..HEAD", args)
        self.assertNotIn(DEFAULT_REVISION_RANGE, args)

    def test_default_spec_still_uses_main(self) -> None:
        # Sanity check: legacy single-repo deployments keep using `main`
        # because the default spec's `base_branch` is `main`.
        git = _GitRecorder()
        self._read_subject(git, _spec())
        args, _cwd = git.calls[0]
        self.assertIn(DEFAULT_REVISION_RANGE, args)

    def test_uses_per_spec_remote_name(self) -> None:
        # Multi-remote target clones (e.g. public `origin` + private fork
        # `private`) need the rev range to reference the configured remote.
        git = _GitRecorder("feat: hi\n")
        self._read_subject(git, _spec(remote_name="private"))
        args, _cwd = git.calls[0]
        self.assertIn("private/main..HEAD", args)
        self.assertNotIn(DEFAULT_REVISION_RANGE, args)

    def _read_subject(self, git: _GitRecorder, spec) -> str:
        with patch.object(commands, GIT_HELPER, git):
            return probes._first_commit_subject(spec, WORKTREE)


class BranchAheadBehindTest(unittest.TestCase):
    """`_branch_ahead_behind` reads `rev-list --left-right --count` against
    the remote-tracking ref and folds every unreadable answer to `(0, 0)`, so
    a transient git failure cannot re-route the workflow on invented
    divergence."""

    def test_left_right_counts_map_to_ahead_behind(self) -> None:
        # `<remote>/<branch>...HEAD` puts the remote-only count on the left,
        # so the left field is `behind` and the right field is `ahead`.
        git = _GitRecorder("2\t3\n")
        self.assertEqual(self._counts(git), (3, 2))
        args, _cwd = git.calls[0]
        self.assertIn(f"refs/remotes/private/{BRANCH}...HEAD", args)

    def test_git_error_reports_no_divergence(self) -> None:
        git = _GitRecorder("1\t1\n", returncode=1, stderr="fatal: bad revision")
        self.assertEqual(self._counts(git), NO_DIVERGENCE)

    def test_unreadable_output_reports_no_divergence(self) -> None:
        for stdout in ("", "4\n", "one\ttwo\n", "1\t2\t3\n"):
            with self.subTest(stdout=stdout):
                self.assertEqual(
                    self._counts(_GitRecorder(stdout)),
                    NO_DIVERGENCE,
                )

    def _counts(self, git: _GitRecorder) -> tuple:
        with patch.object(commands, HARDENED_HELPER, git):
            return probes._branch_ahead_behind(
                _spec(remote_name="private"), WORKTREE, BRANCH,
            )


if __name__ == "__main__":
    unittest.main()
