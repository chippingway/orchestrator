# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, package-surface, and inventory checks for the worktrees owners."""

from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module
from importlib.util import find_spec

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

_PACKAGE = "orchestrator"

# The spelling that answers as a logger and nowhere else: nothing resolves at
# it as a module and no inventory in the package may name it as the module a
# hub reads a name off, but it is still the channel the owners report on.
_LIFECYCLE_SPELLING = "orchestrator.worktree_lifecycle"

# The aggregate spelling over every git domain at once, held to the same rule
# minus the logger.
_AGGREGATE_HUB = "orchestrator.worktrees"

_ABSENT_TARGETS = (_AGGREGATE_HUB, _LIFECYCLE_SPELLING)

_MODULES = (
    "orchestrator.git.worktrees",
    "orchestrator.git.worktrees.cleanup",
    "orchestrator.git.worktrees.creation",
    "orchestrator.git.worktrees.decomposition",
    "orchestrator.git.worktrees.paths",
    "orchestrator.git.worktrees.recovery",
    "orchestrator.git.worktrees.terminal",
)

# The module paths a second import site for these owners would take: the two
# spellings themselves, and the inventory and resolver hooks either one would
# be built from.
_FLAT_MODULES = (
    "orchestrator._worktree_lifecycle_export_manifest",
    "orchestrator._worktree_lifecycle_exports",
    "orchestrator._worktrees_export_manifest",
    "orchestrator._worktrees_exports",
    _AGGREGATE_HUB,
    _LIFECYCLE_SPELLING,
)

# The initializer binds nothing, so each name answers on the owner that defines
# it, never on the package itself.
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

# Every name the owners define, paired with the owner that defines it: the slug
# pattern and the digest math behind it, the two sanitizers, the branch, root,
# and worktree-path derivations and the pinned / legacy resolver, the
# candidate-branch and commit-count reads behind the unpushed-commit probe, the
# two creators, the new-commit probe, and the `worktree` argv they run, the
# decomposer's path, creation, and removal, the per-issue removal and local
# branch deletion, and the two teardowns composed from them. Naming the whole
# surface makes a helper added to an owner an edit here rather than a
# definition site nothing checks.
_OWNER_DEFINED = (
    ("_SAFE_CHAR", paths),
    ("_SLUG_DIGEST_LEN", paths),
    ("_SLUG_SAFE_RE", paths),
    ("_WORKTREE_ADD", creation),
    ("_WORKTREE_REMOVE_FORCE", creation),
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

# The owners that report, each binding the channel an operator's level and
# handler selection is keyed on.
_REPORTING_OWNERS = (cleanup, creation, decomposition, terminal)


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
    """The initializer binds nothing and every name answers on its owner."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(_worktrees_package, owner_only_name)

    def test_every_name_is_defined_on_its_owner(self) -> None:
        # A helper lifted onto a sibling would still resolve for its callers,
        # so the defining module is what a patch aimed at the teardown ordering
        # or the digest math behind a slug has to land on.
        for owner_name, owner in _OWNER_DEFINED:
            with self.subTest(name=owner_name):
                self.assertIn(owner_name, owner.__dict__)


class OwnerImportSiteTest(unittest.TestCase):
    """No surface over these owners sits beside them."""

    def test_no_flat_module_exists(self) -> None:
        # Anything importable at these paths would be a second identity for the
        # branch and path derivations every worktree is created and torn down
        # by -- free to drift from the owner silently and invisible to a patch
        # aimed at it. Resolving the spec rather than stat-ing one path catches
        # a copy planted anywhere the interpreter would find it.
        for module in _FLAT_MODULES:
            with self.subTest(module=module):
                self.assertIsNone(find_spec(module))

    def test_no_inventory_targets_an_absent_spelling(self) -> None:
        # Nothing resolves at either spelling, so an inventory naming one is a
        # dead target that stays quiet until whichever caller reads that name
        # runs. Scanning every inventory in the package is what surfaces it
        # before then.
        for inventory_name in inventory_modules(_PACKAGE):
            inventory = import_module(inventory_name)
            targets = {target.module_name for target in inventory.EXPORTS}
            for absent in _ABSENT_TARGETS:
                with self.subTest(inventory=inventory_name, target=absent):
                    self.assertNotIn(absent, targets)


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


if __name__ == "__main__":
    unittest.main()
