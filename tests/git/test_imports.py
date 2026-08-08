# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, package-surface, and inventory checks for the git package."""

from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module
from importlib.util import find_spec
from types import MappingProxyType

from orchestrator import _worktree_lifecycle_export_manifest, _worktrees_export_manifest
from orchestrator import git as _git_package
from orchestrator.git import commands, locks
from tests.git.inventory_test_support import inventory_modules
from tests.reexport_test_support import lazy_targets

_PACKAGE = "orchestrator"

# The flat spelling of the plumbing surface, which no inventory in the package
# may name as the module a hub resolves one of these names off.
_PLUMBING_FACADE = "orchestrator.git_plumbing"

_MODULES = (
    "orchestrator.git",
    "orchestrator.git.authentication",
    "orchestrator.git.commands",
    "orchestrator.git.locks",
)

# The module paths a second import site for these owners would take: the flat
# spelling itself, and the inventory and resolver hooks one would be built from.
_FLAT_MODULES = (
    "orchestrator._git_plumbing_export_manifest",
    "orchestrator._git_plumbing_exports",
    _PLUMBING_FACADE,
)

# The plain runner and the per-root lock, named once because each recurs in the
# owner surface and in both hub slices below.
_PLAIN_GIT = "_git"

_ROOT_LOCK = "_target_root_lock"

# The initializer binds nothing, so each name answers on the owner that defines
# it and on the hubs above the package, never on the package itself.
_OWNER_ONLY_NAMES = (
    "TargetRootLockRegistry",
    "_TARGET_ROOT_LOCKS",
    "_authed_fetch",
    _PLAIN_GIT,
    "_git_auth_session",
    "_git_hardened",
    "_push_branch",
    _ROOT_LOCK,
    "_unsafe_local_transport_config",
)

# The plumbing names each aggregate facade above the package republishes,
# paired with the owner that defines them.
_HUB_PUBLISHED = MappingProxyType({
    "orchestrator.worktree_lifecycle": (
        (_PLAIN_GIT, commands),
        (_ROOT_LOCK, locks),
    ),
    "orchestrator.worktrees": (
        ("_GIT_NO_PROMPT_ENV", commands),
        ("_TARGET_ROOT_LOCKS", locks),
        ("_TARGET_ROOT_LOCKS_LOCK", locks),
        (_PLAIN_GIT, commands),
        ("_git_hardened", commands),
        (_ROOT_LOCK, locks),
    ),
})

# Each hub's inventory keyed the same way, so one lookup carries both the module
# a name is declared to resolve off and the object the hub hands back.
_HUB_INVENTORIES = MappingProxyType({
    "orchestrator.worktree_lifecycle": lazy_targets(_worktree_lifecycle_export_manifest),
    "orchestrator.worktrees": lazy_targets(_worktrees_export_manifest),
})

_HUB_LOOKUPS = tuple(
    (facade_name, export_name, owner)
    for facade_name, published in _HUB_PUBLISHED.items()
    for export_name, owner in published
)


class CleanProcessImportTest(unittest.TestCase):
    """Each git module imports standalone in a fresh interpreter.

    The owners bind their in-package collaborators eagerly, so importing any
    one of them first must not need a name a half-run module has not defined
    yet. A subprocess per module gives each a clean `sys.modules` no other
    test has already populated, exposing an import-order cycle a package-first
    suite run would mask.
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
    """The initializer carries no bindings of its own."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(_git_package, owner_only_name)


class OwnerImportSiteTest(unittest.TestCase):
    """No module of this domain's own sits beside the owners."""

    def test_no_flat_module_exists(self) -> None:
        # Anything importable at these paths would be a second identity for the
        # hardened argv prefixes every git call is spawned with and the
        # per-root lock the worktree mutations serialize under -- free to drift
        # from the owner silently and invisible to a patch aimed at it.
        # Resolving the spec rather than stat-ing one path catches a copy
        # planted anywhere the interpreter would find it.
        for module in _FLAT_MODULES:
            with self.subTest(module=module):
                self.assertIsNone(find_spec(module))


class AggregateInventoryTest(unittest.TestCase):
    """The hubs above the package resolve plumbing names off the owners."""

    def test_each_hub_names_the_owner(self) -> None:
        # A hub reading a forwarder of an owner would hand back the same
        # object, so the declared target is what separates one from a hub
        # reading the owner itself -- and only the second keeps a patch aimed
        # at the owner and one aimed at the hub two interceptions rather than
        # three.
        for facade_name, export_name, owner in _HUB_LOOKUPS:
            with self.subTest(facade=facade_name, name=export_name):
                target = _HUB_INVENTORIES[facade_name][export_name]
                self.assertEqual(target.module_name, owner.__name__)
                self.assertIs(
                    getattr(import_module(facade_name), export_name),
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
                    _PLUMBING_FACADE,
                    {target.module_name for target in inventory.EXPORTS},
                )


if __name__ == "__main__":
    unittest.main()
