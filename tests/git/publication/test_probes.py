# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Subject-shape predicates, commit-subject reads, and one divergence reading."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

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

REV_PARSE = "rev-parse"

# The tip the fetched ref resolves to, and the commit something moves it to
# while the reading is being taken.
TIP = "1ec04e5e" * 5
MOVED_TIP = "cafe1234" * 5

# Every reading that did not happen, which is what no caller may act on.
UNREADABLE = probes._BranchDivergence()


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


class _ResolvesThenCounts:
    """A git double answering the two commands one divergence reading makes.

    The ref resolve first, then the comparison, so a case can say what each
    one answered. `tips` may name MORE than one: a ref something moves while
    the reading is being taken answers the next resolve differently, which is
    what a second one would have got.
    """

    def __init__(self, *tips: str, counts: str = "0\t0\n") -> None:
        self.calls: list[tuple] = []
        self._tips = list(tips)
        self._counts = counts

    def __call__(self, *args, cwd):
        self.calls.append((args, cwd))
        if args[0] != REV_PARSE:
            return _git_answer(self._counts)
        answered = self._tips[0]
        if len(self._tips) > 1:
            self._tips.pop(0)
        return _git_answer(answered)

    @property
    def resolves(self) -> int:
        """How many times the ref was asked what it points at."""
        asked = [args for args, _cwd in self.calls if args[0] == REV_PARSE]
        return len(asked)


def _git_answer(stdout: str, *, returncode: int = 0):
    """One completed git invocation, as the probe reads it."""
    return MagicMock(returncode=returncode, stdout=stdout, stderr="")


class _RefusesTheComparison(_ResolvesThenCounts):
    """A ref that resolves and a comparison git will not take."""

    def __call__(self, *args, cwd):
        self.calls.append((args, cwd))
        if args[0] == REV_PARSE:
            return _git_answer(TIP)
        return _git_answer("", returncode=1)


class BranchDivergenceTest(unittest.TestCase):
    """One reading: the ref resolved once, then HEAD counted against it.

    The two commands are one fact, and the commit is why. The counts are a
    claim about the tip they were taken against, and the push that claim
    licenses is pinned to that same commit -- so a ref something moves in
    between must not leave the branch proved against one head and the push
    pinned to another.
    """

    def test_the_comparison_names_the_resolved_commit(self) -> None:
        # Not the ref. Named the ref, a fetch racing this reading would have
        # the counts taken against a tip the caller never reports -- and the
        # push it licenses would be leased to a head nothing compared.
        git = _ResolvesThenCounts(TIP, counts="2\t3\n")

        divergence = self._divergence(git)

        self.assertEqual(divergence.tip, TIP)
        # `<tip>...HEAD` puts the tip-only count on the left, so the left
        # field is `behind` and the right field is `ahead`.
        self.assertEqual((divergence.ahead, divergence.behind), (3, 2))
        self.assertTrue(divergence.readable)
        counted, _cwd = git.calls[1]
        self.assertIn(f"{TIP}...HEAD", counted)
        self.assertNotIn(f"refs/remotes/private/{BRANCH}...HEAD", counted)

    def test_a_ref_that_moves_is_resolved_once(self) -> None:
        # The race this reading closes: the ref is at H0 when the comparison
        # is taken and at H1 a moment later. Asked twice -- once to compare
        # against and once to name -- the counts would be about H0 while the
        # head reported, and therefore the lease the push is pinned to, is
        # H1: where the pull request has moved to H1 too, that lease is
        # satisfied and the force-push lands on top of it.
        git = _ResolvesThenCounts(TIP, MOVED_TIP, counts="0\t1\n")

        divergence = self._divergence(git)

        self.assertEqual(git.resolves, 1)
        self.assertEqual(divergence.tip, TIP)
        counted, _cwd = git.calls[1]
        self.assertIn(f"{TIP}...HEAD", counted)

    def test_an_in_sync_branch_is_readable(self) -> None:
        # What says every refusal above is about the reading rather than
        # about zero counts: in sync is zero and zero AND readable.
        divergence = self._divergence(_ResolvesThenCounts(TIP))

        self.assertTrue(divergence.readable)
        self.assertEqual((divergence.ahead, divergence.behind), (0, 0))

    def test_a_reading_that_did_not_happen_refuses(self) -> None:
        # Every way one of the two commands can fail to answer, and none of
        # them is `(0, 0)`: read as an in-sync branch, a stale checkout is
        # rebased, spawned over, and force-pushed on evidence nobody took.
        refused = (
            _GitRecorder("", returncode=1, stderr="fatal: bad revision"),
            _GitRecorder("\n"),
            _RefusesTheComparison(TIP),
            *(
                _ResolvesThenCounts(TIP, counts=counts)
                for counts in ("", "4\n", "one\ttwo\n", "1\t2\t3\n")
            ),
        )
        for git in refused:
            with self.subTest(git=type(git).__name__):
                self.assertEqual(self._divergence(git), UNREADABLE)

    def _divergence(self, git):
        with patch.object(commands, HARDENED_HELPER, git):
            return probes._branch_divergence(
                _spec(remote_name="private"), WORKTREE, BRANCH,
            )


if __name__ == "__main__":
    unittest.main()
