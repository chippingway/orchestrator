# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Slug sanitization plus worktree path and branch derivation."""

from __future__ import annotations

import unittest
from pathlib import Path

from orchestrator import config
from orchestrator.git.worktrees import paths

from tests.git.worktrees.path_test_support import (
    ALICE_REPO_SLUG,
    BASE_BRANCH,
    BOB_REPO_SLUG,
    PR_NUMBER,
    SHARED_BRANCH_ISSUE_NUMBER,
    _migration_spec,
    _spec,
)

SHARED_CLONE_ROOT = Path("/tmp/shared-clone")


class WorktreePathSlugNamespaceTest(unittest.TestCase):
    """Two repos with the same issue number must produce distinct worktree
    paths, otherwise simultaneous orchestration of both would have them
    fighting over the same `WORKTREES_DIR/issue-N` checkout. The slug
    sanitizer also has to produce a single filesystem-safe segment
    (no `/`, no leading `.`) since it becomes a directory name.
    """

    def test_distinct_slugs_same_number_never_collide(self) -> None:
        spec_a = _spec(ALICE_REPO_SLUG)
        spec_b = _spec(BOB_REPO_SLUG)
        path_a = paths._worktree_path(spec_a, 7)
        path_b = paths._worktree_path(spec_b, 7)

        self.assertNotEqual(path_a, path_b)
        # Both must live under WORKTREES_DIR with the issue-N leaf.
        self.assertEqual(path_a.name, "issue-7")
        self.assertEqual(path_b.name, "issue-7")
        self.assertEqual(path_a.parent.parent, config.WORKTREES_DIR)
        self.assertEqual(path_b.parent.parent, config.WORKTREES_DIR)


class SanitizeSlugTest(unittest.TestCase):
    def test_sanitize_slug_replaces_owner_separator(self) -> None:
        self.assertEqual(paths._sanitize_slug("owner/name"), "owner__name")

    def test_sanitize_slug_is_a_single_segment(self) -> None:
        # A directory name with `/` would split into nested directories,
        # defeating the point of namespacing.
        for raw in (
            "owner/name",
            "deep/owner/name",
            "name-only",
            "weird name with spaces",
        ):
            cleaned = paths._sanitize_slug(raw)
            self.assertNotIn("/", cleaned, f"slug={raw!r} -> {cleaned!r}")

    def test_sanitize_slug_no_leading_dot(self) -> None:
        # Hidden directories (.foo) hide the worktree from a casual
        # operator inspection; escape leading dots.
        self.assertFalse(paths._sanitize_slug(".dotfile/repo").startswith("."))
        self.assertFalse(paths._sanitize_slug("./repo").startswith("."))

    def test_sanitize_slug_strips_unsafe_chars(self) -> None:
        cleaned = paths._sanitize_slug("owner@#$/name with spaces")
        # No path separator, no shell-special chars; only [A-Za-z0-9_.-]
        for ch in cleaned:
            self.assertTrue(
                ch.isalnum() or ch in "_.-",
                f"unexpected char {ch!r} in {cleaned!r}",
            )

    def test_sanitize_slug_empty_input_falls_back(self) -> None:
        # Empty would collapse `WORKTREES_DIR/<slug>/issue-N` into
        # `WORKTREES_DIR/issue-N`, reintroducing the cross-repo collision.
        self.assertNotEqual(paths._sanitize_slug(""), "")
        self.assertNotEqual(paths._sanitize_slug(""), ".")

    def test_default_repo_spec_path_format(self) -> None:
        # Anchor the documented `<owner>__<name>/issue-N` layout.
        path = paths._worktree_path(_migration_spec(), 9)
        self.assertEqual(
            path,
            config.WORKTREES_DIR / "chippingway__orchestrator" / "issue-9",
        )


class BranchNameSlugNamespaceTest(unittest.TestCase):
    """Two RepoSpecs that share the same `target_root` (a single local
    clone with multiple remotes) would otherwise collide on
    `orchestrator/issue-N` because git refuses to check the same branch
    out in two worktrees of one repo. `_branch_name` includes the
    sanitized slug so each spec lives on its own branch.
    """

    def test_same_number_distinct_slugs_make_branches(self) -> None:
        spec_a = config.RepoSpec(
            slug="geserdugarov/lance-open-source",
            target_root=SHARED_CLONE_ROOT,
            base_branch=BASE_BRANCH,
        )
        spec_b = config.RepoSpec(
            slug="geserdugarov/lance-private",
            target_root=SHARED_CLONE_ROOT,
            base_branch=BASE_BRANCH,
        )

        self.assertNotEqual(
            paths._branch_name(spec_a, SHARED_BRANCH_ISSUE_NUMBER),
            paths._branch_name(spec_b, SHARED_BRANCH_ISSUE_NUMBER),
        )

    def test_branch_name_format(self) -> None:
        self.assertEqual(
            paths._branch_name(_migration_spec(), 9),
            "orchestrator/chippingway__orchestrator/issue-9",
        )

    def test_branch_name_keeps_orchestrator_prefix(self) -> None:
        # `_cleanup_terminal_branch` relies on the `orchestrator/` prefix
        # to constrain what branches it is willing to delete.
        for repo_slug in (ALICE_REPO_SLUG, BOB_REPO_SLUG, "weird name/x"):
            self.assertTrue(
                paths._branch_name(
                    _spec(repo_slug), PR_NUMBER,
                ).startswith("orchestrator/"),
                repo_slug,
            )


if __name__ == "__main__":
    unittest.main()
