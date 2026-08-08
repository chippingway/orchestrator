# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, package-surface, and inventory checks for the worktrees owners."""

from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module
from importlib.util import find_spec

from orchestrator import _worktrees_export_manifest, worktrees
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

# The one spelling that outlives the flat module: nothing resolves there and no
# inventory in the package may name it as the module a hub reads a name off,
# but it is still the logger the owners report on.
_LIFECYCLE_SPELLING = "orchestrator.worktree_lifecycle"

_MODULES = (
    "orchestrator.git.worktrees",
    "orchestrator.git.worktrees.cleanup",
    "orchestrator.git.worktrees.creation",
    "orchestrator.git.worktrees.decomposition",
    "orchestrator.git.worktrees.paths",
    "orchestrator.git.worktrees.recovery",
    "orchestrator.git.worktrees.terminal",
)

# The module paths a second import site for these owners would take: the flat
# spelling itself, and the inventory and resolver hooks one would be built from.
_FLAT_MODULES = (
    "orchestrator._worktree_lifecycle_export_manifest",
    "orchestrator._worktree_lifecycle_exports",
    _LIFECYCLE_SPELLING,
)

# The initializer binds nothing, so each name answers on the owner that defines
# it and on the hub above the package, never on the package itself.
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

# Every remaining name the owners define, which the hub deliberately leaves
# out: the removal and branch-deletion steps and the argv they run, the
# decomposer's own removal runner, the candidate-branch and commit-count reads,
# and the digest internals behind a slug. Naming them keeps the boundary
# between an owner's own definitions and the slice the hub carries asserted
# rather than assumed.
_OWNER_DEFINED = (
    ("_SAFE_CHAR", paths),
    ("_SLUG_DIGEST_LEN", paths),
    ("_WORKTREE_ADD", creation),
    ("_WORKTREE_REMOVE_FORCE", creation),
    ("_branch_commit_count", recovery),
    ("_candidate_issue_branches", recovery),
    ("_commit_count_from_stdout", recovery),
    ("_delete_local_issue_branch", cleanup),
    ("_remove_issue_worktree", cleanup),
    ("_run_decompose_worktree_removal", decomposition),
    ("_run_issue_worktree_removal", cleanup),
    ("_run_local_branch_deletion", cleanup),
    ("_slug_digest", paths),
)

# The owners that report, each binding the channel an operator's level and
# handler selection is keyed on.
_REPORTING_OWNERS = (cleanup, creation, decomposition, terminal)

_HUB_INVENTORY = lazy_targets(_worktrees_export_manifest)


class CleanProcessImportTest(unittest.TestCase):
    """Each owner imports standalone in a fresh interpreter.

    Every owner depends only on config, pinned state, the git command /
    lock / authentication owners, and its in-package siblings, so importing
    any one of them first must not need a name a half-run module has not
    defined yet. A subprocess per module gives each a clean `sys.modules` no
    other test has already populated, exposing an import-order cycle a
    package-first suite run would mask.
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
    """The initializer binds nothing and the unpublished names stay owner-only."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(_worktrees_package, owner_only_name)

    def test_unpublished_names_stay_owner_only(self) -> None:
        # The hub slice below is a deliberate surface rather than the whole
        # package: these names have no second import site at all, so the
        # teardown ordering and the digest math behind a slug stay reachable
        # only where they are defined.
        for owner_name, owner in _OWNER_DEFINED:
            with self.subTest(name=owner_name):
                self.assertIn(owner_name, owner.__dict__)
                self.assertNotIn(owner_name, _HUB_INVENTORY)


class OwnerImportSiteTest(unittest.TestCase):
    """No module of this domain's own sits beside the owners."""

    def test_no_flat_module_exists(self) -> None:
        # Anything importable at these paths would be a second identity for the
        # branch and path derivations every worktree is created and torn down
        # by -- free to drift from the owner silently and invisible to a patch
        # aimed at it. Resolving the spec rather than stat-ing one path catches
        # a copy planted anywhere the interpreter would find it.
        for module in _FLAT_MODULES:
            with self.subTest(module=module):
                self.assertIsNone(find_spec(module))


class ReportingChannelTest(unittest.TestCase):
    """Every owner that logs reports on the operator-facing channel.

    Operators filter on the rendered prefix and attach handlers to it, so a
    logger renamed after its own module path would silently drop that
    owner's worktree and branch teardown lines out of their filters.
    """

    def test_owners_keep_the_operator_name(self) -> None:
        for owner in _REPORTING_OWNERS:
            with self.subTest(owner=owner.__name__):
                self.assertEqual(owner.log.name, _LIFECYCLE_SPELLING)


class AggregateInventoryTest(unittest.TestCase):
    """The hub above the package resolves worktree names off the owners."""

    def test_the_hub_names_the_owner(self) -> None:
        # A hub reading a forwarder of an owner would hand back the same
        # object, so the declared target is what separates one from a hub
        # reading the owner itself -- and only the second keeps a patch aimed
        # at the owner and one aimed at the hub two interceptions rather than
        # three.
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

    def test_no_inventory_targets_the_flat_spelling(self) -> None:
        # Nothing resolves at the flat spelling, so an inventory naming it is a
        # dead target that stays quiet until whichever caller reads that one
        # name off the hub runs. Scanning every inventory in the package is
        # what surfaces it before then.
        for inventory_name in inventory_modules(_PACKAGE):
            with self.subTest(inventory=inventory_name):
                inventory = import_module(inventory_name)
                self.assertNotIn(
                    _LIFECYCLE_SPELLING,
                    {target.module_name for target in inventory.EXPORTS},
                )


if __name__ == "__main__":
    unittest.main()
