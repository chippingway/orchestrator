# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, package-surface, and inventory checks for the git package."""

from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module
from importlib.util import find_spec

from orchestrator import git as _git_package
from orchestrator.git import (
    branch_transport,
    commands,
    credentials,
    locks,
    ref_transport,
)
from tests.git.inventory_test_support import inventory_modules

_PACKAGE = "orchestrator"

# The two spellings no inventory in the package may name as the module a hub
# resolves one of these names off: the flat plumbing surface of this domain,
# and the aggregate hub over every git domain at once.
_PLUMBING_FACADE = "orchestrator.git_plumbing"

_AGGREGATE_HUB = "orchestrator.worktrees"

_ABSENT_TARGETS = (_AGGREGATE_HUB, _PLUMBING_FACADE)

# The module the two transports were split out of, retired rather than left
# behind as a facade over them.
_RETIRED_TRANSPORT = "orchestrator.git.authentication"

_MODULES = (
    "orchestrator.git",
    "orchestrator.git.branch_transport",
    "orchestrator.git.commands",
    "orchestrator.git.credentials",
    "orchestrator.git.locks",
    "orchestrator.git.ref_transport",
)

# The module paths a second import site for these owners would take: the two
# spellings themselves, the inventory and resolver hooks either one would be
# built from, and the module the transports were split out of.
_FLAT_MODULES = (
    "orchestrator._git_plumbing_export_manifest",
    "orchestrator._git_plumbing_exports",
    "orchestrator._worktrees_export_manifest",
    "orchestrator._worktrees_exports",
    _AGGREGATE_HUB,
    _PLUMBING_FACADE,
    _RETIRED_TRANSPORT,
)

# The per-root lock and the askpass session, named once each because both
# recur in the owner surface and in the tables below.
_ROOT_LOCK = "_target_root_lock"

_AUTH_SESSION = "_git_auth_session"

# The one remote read both transports answer a lease with, named once because
# it recurs in the owner surface and in the binding assertion below.
_REF_READ = "_remote_ref_read"

# The initializer binds nothing, so each name answers on the owner that defines
# it, never on the package itself.
_OWNER_ONLY_NAMES = (
    "TargetRootLockRegistry",
    "_TARGET_ROOT_LOCKS",
    "_authed_fetch",
    "_delete_remote_ref",
    "_git",
    _AUTH_SESSION,
    "_git_hardened",
    "_push_branch",
    "_push_ref",
    _REF_READ,
    "_remote_ref_sha",
    _ROOT_LOCK,
    "_unsafe_local_transport_config",
)

# The plumbing no caller outside the package reaches for, paired with the owner
# that defines it: the no-prompt environment every git call is spawned with and
# the whole per-target-root lock surface. Naming them keeps each owner's own
# definitions asserted rather than assumed.
_OWNER_DEFINED = (
    ("_GIT_NO_PROMPT_ENV", commands),
    ("_TARGET_ROOT_LOCKS", locks),
    ("_TARGET_ROOT_LOCKS_LOCK", locks),
    (_ROOT_LOCK, locks),
)

# What the credential owner defines and the transport only spends: the record
# a token-bearing call is built from, the session that yields one, and the
# per-repository lookup behind it.
_CREDENTIAL_NAMES = ("_GitAuthSession", _AUTH_SESSION, "_resolved_git_token")


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
    """The initializer binds nothing and the unpublished names stay owner-only."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name), self.assertRaises(AttributeError):
                getattr(_git_package, owner_only_name)


    def test_unpublished_names_stay_owner_only(self) -> None:
        # The workflow slice is a deliberate surface rather than the whole
        # package: these names have no second import site at all, so the
        # environment every git call is spawned with and the lock the worktree
        # mutations serialize under stay reachable only where they are defined.
        for owner_name, owner in _OWNER_DEFINED:
            with self.subTest(name=owner_name):
                self.assertIn(owner_name, owner.__dict__)


class OwnerImportSiteTest(unittest.TestCase):
    """No surface over these owners sits beside them."""

    def test_credential_names_have_one_binding(self) -> None:
        # Each transport reaches these through the module rather than
        # importing them by name. A second binding on either would be a patch
        # target that reads as the right one and intercepts nothing, since the
        # session a call actually opens would still be the owner's.
        for credential_name in _CREDENTIAL_NAMES:
            for spender in (branch_transport, ref_transport):
                with self.subTest(name=credential_name, owner=spender):
                    self.assertIn(credential_name, credentials.__dict__)
                    self.assertNotIn(credential_name, spender.__dict__)

    def test_the_remote_read_has_one_binding(self) -> None:
        # A branch tip and a whole refname are the same `ls-remote`, so the
        # branch transport spends the ref owner's read rather than keeping one
        # of its own. A copy beside the caller would be the patch target a test
        # aims at while the read a push actually takes stayed the owner's.
        self.assertIn(_REF_READ, ref_transport.__dict__)
        self.assertNotIn(_REF_READ, branch_transport.__dict__)

    def test_no_flat_module_exists(self) -> None:
        # Anything importable at these paths would be a second identity for the
        # hardened argv prefixes every git call is spawned with, the per-root
        # lock the worktree mutations serialize under, or the transport the two
        # owners were split out of -- free to drift from the owner silently and
        # invisible to a patch aimed at it.
        # Resolving the spec rather than stat-ing one path catches a copy
        # planted anywhere the interpreter would find it.
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


if __name__ == "__main__":
    unittest.main()
