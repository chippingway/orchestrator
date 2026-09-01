# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Prefix inference and PR-title selection on the `titles` owner."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.git import commands
from orchestrator.git.publication import titles
from tests.git.publication.publication_helpers import (
    FEATURE_PREFIX,
    GIT_HELPER,
    WORKTREE,
    _GitRecorder,
    _spec,
)
from tests.support.fakes import FakeLabel, make_issue

PREFIX_HELPER_ISSUE = 50
GIT_ERROR_ISSUE = 51
REMOTE_ROUTING_ISSUE = 52
TITLE_ISSUE = 53
ISSUE_TITLE = "add a sparkly thing"


class _InferFixtureMixin:
    def _infer(
        self,
        git: _GitRecorder,
        *,
        bug: bool = False,
        spec=None,
        number: int = PREFIX_HELPER_ISSUE,
    ) -> str:
        issue = make_issue(number, title="do a thing")
        if bug:
            issue.labels.append(FakeLabel("bug"))
        with patch.object(commands, GIT_HELPER, git):
            return titles._infer_subject_prefix(
                spec or _spec(),
                WORKTREE,
                issue,
            )


class InferSubjectPrefixTest(unittest.TestCase, _InferFixtureMixin):
    """`_infer_subject_prefix` reads recent base-branch history and reuses a
    dominant repo-local prefix; otherwise it falls back to `fix` for
    bug-labelled issues and `feat` everywhere else."""

    def test_dominant_repo_local_prefix_is_reused(self) -> None:
        # Events repo: `event:` dominates, so the fallback honors it.
        self.assertEqual(
            self._infer(_GitRecorder("event: gala\nevent: meetup\nfeat: tooling\n")),
            "event",
        )

    def test_repo_local_prefix_overrides_bug_label(self) -> None:
        # The repo's own style wins even for a bug-labelled issue -- a repo
        # that doesn't use `fix:` shouldn't suddenly get one.
        self.assertEqual(
            self._infer(_GitRecorder("event: gala\nevent: meetup\n"), bug=True),
            "event",
        )

    def test_conventional_history_keeps_feat_default(self) -> None:
        # When the dominant prefix is itself a Conventional type, defer to
        # the bug/feat heuristic rather than echoing the history prefix.
        self.assertEqual(
            self._infer(_GitRecorder("feat: a\nfix: b\nfeat: c\n")),
            FEATURE_PREFIX,
        )

    def test_conventional_history_bug_label_uses_fix(self) -> None:
        self.assertEqual(
            self._infer(_GitRecorder("feat: a\nfeat: b\n"), bug=True),
            "fix",
        )

    def test_empty_history_falls_back_to_feat(self) -> None:
        self.assertEqual(self._infer(_GitRecorder()), FEATURE_PREFIX)

    def test_unprefixed_history_falls_back_to_feat(self) -> None:
        # History with no `<prefix>:` subjects yields no dominant prefix.
        self.assertEqual(
            self._infer(_GitRecorder("initial commit\nmore work\n")),
            FEATURE_PREFIX,
        )


class InferSubjectPrefixGitRoutingTest(unittest.TestCase, _InferFixtureMixin):
    def test_git_error_falls_back_without_crashing(self) -> None:
        git = _GitRecorder(returncode=1, stderr="fatal: bad revision")
        self.assertEqual(
            self._infer(git, number=GIT_ERROR_ISSUE),
            FEATURE_PREFIX,
        )

    def test_reads_per_spec_base_and_remote(self) -> None:
        git = _GitRecorder("event: x\n")
        self._infer(
            git,
            spec=_spec(base_branch="master", remote_name="private"),
            number=REMOTE_ROUTING_ISSUE,
        )
        args, _cwd = git.calls[0]
        # The history log targets `<remote>/<base>`, honoring the spec.
        self.assertIn("private/master", args)
        self.assertNotIn("origin/main", args)


class PrTitleSelectionTest(unittest.TestCase):
    """`_pr_title_from_commit_or_issue` prefers the agent's own commit
    subject, then the issue title when either already carries a reusable
    `<prefix>:` form, and only otherwise synthesizes one from the fallback
    prefix. The title stays free of the issue reference -- the `Resolves #<n>`
    line in the PR body carries traceability."""

    def test_reusable_commit_subject_is_kept_verbatim(self) -> None:
        for subject in (
            "feat: add a sparkly thing",
            "fix(api)!: drop legacy endpoint",  # scope and breaking marker
            "event: add the winter gala",  # repo-local, not a Conventional type
        ):
            with self.subTest(subject=subject):
                self.assertEqual(self._title(subject), subject)

    def test_prefixed_issue_title_is_reused(self) -> None:
        # An already-prefixed issue title must not gain a second prefix.
        self.assertEqual(
            self._title(
                "some unconventional commit",
                title="docs: clarify the README",
            ),
            "docs: clarify the README",
        )

    def test_unprefixed_pair_synthesizes_from_default(self) -> None:
        self.assertEqual(
            self._title("updated stuff"),
            f"{FEATURE_PREFIX}: {ISSUE_TITLE}",
        )

    def test_synthesized_title_honors_fallback_prefix(self) -> None:
        # The repo-local prefix `_infer_subject_prefix` read from base
        # history reaches the synthesized subject.
        self.assertEqual(
            self._title("updated the listings", prefix="career"),
            f"career: {ISSUE_TITLE}",
        )

    def test_titleless_issue_falls_back_to_its_number(self) -> None:
        self.assertEqual(
            self._title("", title=""),
            f"{FEATURE_PREFIX}: address issue #{TITLE_ISSUE}",
        )

    def _title(
        self,
        first_subject: str,
        *,
        title: str = ISSUE_TITLE,
        prefix: str = "",
    ) -> str:
        issue = make_issue(TITLE_ISSUE, title=title)
        if not prefix:
            # Exercise the `feat` default the callers rely on.
            return titles._pr_title_from_commit_or_issue(issue, first_subject)
        return titles._pr_title_from_commit_or_issue(
            issue, first_subject, prefix,
        )


if __name__ == "__main__":
    unittest.main()
