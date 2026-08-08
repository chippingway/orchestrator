# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, package-surface, and inventory checks for the worktrees owners."""

from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module

from orchestrator import _worktrees_export_manifest, worktree_lifecycle, worktrees
from orchestrator.git import worktrees as _worktrees_package
from orchestrator.git.worktrees import (
    cleanup,
    creation,
    decomposition,
    paths,
    recovery,
    terminal,
)
from tests.git.inventory_test_support import inventory_modules
from tests.reexport_test_support import lazy_targets

_PACKAGE = "orchestrator"

_LIFECYCLE_FACADE = "orchestrator.worktree_lifecycle"

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

# The worktree names the aggregate hub above the package republishes, paired
# with the owner that defines them -- the naming, creation, recovery,
# decomposition, and terminal helpers a stage handler reaches for, and not the
# removal helpers under `cleanup` that `terminal` composes its teardown from.
_HUB_PUBLISHED = (
    ("_SLUG_SAFE_RE", paths),
    ("_branch_has_unpushed_commits", recovery),
    ("_branch_name", paths),
    ("_cleanup_decompose_worktree", decomposition),
    ("_cleanup_question_worktree", terminal),
    ("_cleanup_terminal_branch", terminal),
    ("_decompose_worktree_path", decomposition),
    ("_ensure_decompose_worktree", decomposition),
    ("_ensure_pr_worktree", creation),
    ("_ensure_worktree", creation),
    ("_has_new_commits", creation),
    ("_repo_worktrees_root", paths),
    ("_resolve_branch_name", paths),
    ("_sanitize_branch_segment", paths),
    ("_sanitize_slug", paths),
    ("_worktree_path", paths),
)

_HUB_INVENTORY = lazy_targets(_worktrees_export_manifest)


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


class AggregateInventoryTest(unittest.TestCase):
    """The hub above the package resolves worktree names off the owners."""

    def test_the_hub_names_the_owner(self) -> None:
        # A hop through `worktree_lifecycle` would hand back the same object,
        # so the declared target is what separates a hub reading the owner from
        # one reading a forwarder of it -- and only the first keeps a patch
        # aimed at the owner and one aimed at the hub two interceptions rather
        # than three.
        for export_name, owner in _HUB_PUBLISHED:
            with self.subTest(name=export_name):
                self.assertEqual(
                    _HUB_INVENTORY[export_name].module_name,
                    owner.__name__,
                )
                self.assertIs(
                    getattr(worktrees, export_name),
                    getattr(owner, export_name),
                )

    def test_no_inventory_targets_the_facade(self) -> None:
        # The facade's own inventory names the owners like every other one, so
        # nothing is exempt: a target spelled at the facade would be a second
        # resolution hop for a name whose owner already answers directly.
        for inventory_name in inventory_modules(_PACKAGE):
            with self.subTest(inventory=inventory_name):
                inventory = import_module(inventory_name)
                self.assertNotIn(
                    _LIFECYCLE_FACADE,
                    {target.module_name for target in inventory.EXPORTS},
                )


if __name__ == "__main__":
    unittest.main()
