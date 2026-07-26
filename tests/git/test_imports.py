# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import checks and package surface for the git package."""

from __future__ import annotations

import subprocess
import sys
import unittest

from orchestrator import git as _git_package
from orchestrator import git_plumbing
from orchestrator.git import authentication, commands, locks

_MODULES = (
    "orchestrator.git",
    "orchestrator.git.authentication",
    "orchestrator.git.commands",
    "orchestrator.git.locks",
    "orchestrator.git_plumbing",
)

# The initializer binds nothing, so each name stays reachable only through its
# owner or the historical `git_plumbing` facade.
_OWNER_ONLY_NAMES = (
    "TargetRootLockRegistry",
    "_TARGET_ROOT_LOCKS",
    "_authed_fetch",
    "_git",
    "_git_auth_session",
    "_git_hardened",
    "_push_branch",
    "_target_root_lock",
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
    ("_git", commands),
    ("_git_auth_env", authentication),
    ("_git_auth_session", authentication),
    ("_git_hardened", commands),
    ("_push_branch", authentication),
    ("_push_with_auth", authentication),
    ("_remote_branch_sha", authentication),
    ("_resolved_git_token", authentication),
    ("_target_root_lock", locks),
    ("_unsafe_local_transport_config", commands),
    ("log", authentication),
)


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


if __name__ == "__main__":
    unittest.main()
