# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, package-surface, and inventory checks for the git package."""

from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from orchestrator import _worktree_lifecycle_export_manifest, _worktrees_export_manifest
from orchestrator import git as _git_package
from orchestrator import git_plumbing
from orchestrator.git import authentication, commands, locks
from tests.reexport_test_support import lazy_targets

_PACKAGE = "orchestrator"

_PLUMBING_FACADE = "orchestrator.git_plumbing"

# Every immutable export inventory in the package, which is where a name's
# resolution target is declared.
_INVENTORY_GLOB = "*_export_manifest.py"

_MODULES = (
    "orchestrator.git",
    "orchestrator.git.authentication",
    "orchestrator.git.commands",
    "orchestrator.git.locks",
    "orchestrator.git_plumbing",
)

# The plain runner and the per-root lock, named once because each recurs in the
# owner surface, in the facade forwards, and in both hub slices below.
_PLAIN_GIT = "_git"

_ROOT_LOCK = "_target_root_lock"

# The initializer binds nothing, so each name stays reachable only through its
# owner or the historical `git_plumbing` facade.
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

_FACADE_FORWARDS = (
    ("_ASKPASS_MODE", authentication),
    ("_AUTHED_GIT_PREFIX", commands),
    ("_FETCH", authentication),
    ("_GIT", commands),
    ("_GIT_NO_PROMPT_ENV", commands),
    ("_GitAuthSession", authentication),
    ("_TARGET_ROOT_LOCKS", locks),
    ("_TARGET_ROOT_LOCKS_LOCK", locks),
    ("_UNSAFE_TRANSPORT_CONFIG_RE", commands),
    ("_authed_fetch", authentication),
    ("_authed_target_fetch", authentication),
    ("_failed_fetch", authentication),
    (_PLAIN_GIT, commands),
    ("_git_auth_env", authentication),
    ("_git_auth_session", authentication),
    ("_git_hardened", commands),
    ("_push_branch", authentication),
    ("_push_with_auth", authentication),
    ("_remote_branch_sha", authentication),
    ("_resolved_git_token", authentication),
    (_ROOT_LOCK, locks),
    ("_unsafe_local_transport_config", commands),
    ("log", authentication),
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


def _inventory_modules() -> tuple[str, ...]:
    """Import paths of every export inventory the package carries."""
    package_root = Path(import_module(_PACKAGE).__file__).parent
    return tuple(sorted(
        ".".join(path.relative_to(package_root.parent).with_suffix("").parts)
        for path in package_root.rglob(_INVENTORY_GLOB)
    ))


class CleanProcessImportTest(unittest.TestCase):
    """Each git module imports standalone in a fresh interpreter.

    The owners bind their in-package collaborators eagerly while
    `git_plumbing` forwards back to them, so importing any one of them first
    must not need a name a half-run module has not defined yet. A subprocess
    per module gives each a clean `sys.modules` no other test has already
    populated, exposing an import-order cycle a package-first suite run would
    mask.
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
    """The initializer carries no bindings; `git_plumbing` forwards to owners."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(_git_package, owner_only_name)

    def test_facade_resolves_owner_objects(self) -> None:
        # The facade forwards rather than rebuilding, so code reaching a helper
        # through `git_plumbing` sees the owner's definition.
        for export_name, owner in _FACADE_FORWARDS:
            with self.subTest(name=export_name):
                self.assertIs(
                    getattr(git_plumbing, export_name),
                    getattr(owner, export_name),
                )


class AggregateInventoryTest(unittest.TestCase):
    """The hubs above the package resolve plumbing names off the owners."""

    def test_each_hub_names_the_owner(self) -> None:
        # A hop through `git_plumbing` would hand back the same object, so the
        # declared target is what separates a hub reading the owner from one
        # reading a forwarder of it -- and only the first keeps a patch aimed
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

    def test_no_inventory_targets_the_facade(self) -> None:
        # The facade's own inventory names the owners like every other one, so
        # nothing in the package is exempt: a target spelled at the facade
        # would be a second resolution hop for a name whose owner already
        # answers directly.
        for inventory_name in _inventory_modules():
            with self.subTest(inventory=inventory_name):
                inventory = import_module(inventory_name)
                self.assertNotIn(
                    _PLUMBING_FACADE,
                    {target.module_name for target in inventory.EXPORTS},
                )


if __name__ == "__main__":
    unittest.main()
