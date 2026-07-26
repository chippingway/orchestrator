# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import checks and package surface for the worktrees owners."""

from __future__ import annotations

import subprocess
import sys
import unittest

from orchestrator import worktree_lifecycle
from orchestrator.git import worktrees as _worktrees_package
from orchestrator.git.worktrees import (
    cleanup,
    creation,
    decomposition,
    paths,
    recovery,
    terminal,
)

_MODULES = (
    "orchestrator.git.worktrees",
    "orchestrator.git.worktrees.cleanup",
    "orchestrator.git.worktrees.creation",
    "orchestrator.git.worktrees.decomposition",
    "orchestrator.git.worktrees.paths",
    "orchestrator.git.worktrees.recovery",
    "orchestrator.git.worktrees.terminal",
)

# The initializer binds nothing, so each name stays reachable only through its
# owner or the historical `worktree_lifecycle` facade.
_OWNER_ONLY_NAMES = (
    "_branch_has_unpushed_commits",
    "_branch_name",
    "_cleanup_terminal_branch",
    "_ensure_worktree",
    "_decompose_worktree_path",
    "_remove_issue_worktree",
    "_resolve_branch_name",
    "_sanitize_slug",
    "_worktree_path",
)

_FACADE_FORWARDS = (
    ("_SAFE_CHAR", paths),
    ("_SLUG_DIGEST_LEN", paths),
    ("_SLUG_SAFE_RE", paths),
    ("_branch_commit_count", recovery),
    ("_branch_has_unpushed_commits", recovery),
    ("_branch_name", paths),
    ("_candidate_issue_branches", recovery),
    ("_cleanup_decompose_worktree", decomposition),
    ("_cleanup_question_worktree", terminal),
    ("_cleanup_terminal_branch", terminal),
    ("_commit_count_from_stdout", recovery),
    ("_decompose_worktree_path", decomposition),
    ("_delete_local_issue_branch", cleanup),
    ("_ensure_decompose_worktree", decomposition),
    ("_ensure_pr_worktree", creation),
    ("_ensure_worktree", creation),
    ("_has_new_commits", creation),
    ("_remove_issue_worktree", cleanup),
    ("_repo_worktrees_root", paths),
    ("_resolve_branch_name", paths),
    ("_run_decompose_worktree_removal", decomposition),
    ("_run_issue_worktree_removal", cleanup),
    ("_run_local_branch_deletion", cleanup),
    ("_sanitize_branch_segment", paths),
    ("_sanitize_slug", paths),
    ("_slug_digest", paths),
    ("_worktree_path", paths),
)


class CleanProcessImportTest(unittest.TestCase):
    """Each owner imports standalone in a fresh interpreter.

    Every owner depends only on config, pinned state, the git command /
    lock / authentication owners, and its in-package siblings, so importing
    any one of them first must not need a name a half-run module has not
    defined yet. A subprocess per module gives each a clean `sys.modules` no
    other test has already populated, exposing an import-order cycle a
    facade-first suite run would mask.
    """

    def test_each_module_imports_standalone(self) -> None:
        for module in _MODULES:
            with self.subTest(module=module):
                completed = subprocess.run(
                    [sys.executable, "-c", f"import {module}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)


class PackageSurfaceTest(unittest.TestCase):
    """The initializer carries no bindings; the lifecycle facade forwards."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(_worktrees_package, owner_only_name)

    def test_facade_resolves_owner_objects(self) -> None:
        # The facade forwards rather than rebuilding, so a stage handler
        # reaching a helper through `worktree_lifecycle` -- and the patches
        # aimed at that facade -- see the owner's definition.
        for export_name, owner in _FACADE_FORWARDS:
            with self.subTest(name=export_name):
                self.assertIs(
                    getattr(worktree_lifecycle, export_name),
                    getattr(owner, export_name),
                )


if __name__ == "__main__":
    unittest.main()
