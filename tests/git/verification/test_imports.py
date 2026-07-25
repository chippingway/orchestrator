# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, layering, and facade checks for verification."""

from __future__ import annotations

import subprocess
import sys
import unittest

from orchestrator import git, verify
from orchestrator.git.verification import models, probes

_MODULES = (
    "orchestrator.git.verification",
    "orchestrator.git.verification.models",
    "orchestrator.git.verification.probes",
    "orchestrator._verify_process",
    "orchestrator._verify_runner",
    "orchestrator.verify",
)

# Verification owns result classification for a worktree, so it may reach the
# git command owner and the settings it reads. Anything above that -- the
# workflow engine, its stage handlers, the compatibility facades over them, or
# an application entrypoint -- would invert the dependency and let a `git
# status` probe drag the tick loop into its import graph.
_ALLOWED_ROOTS = ("orchestrator.config", "orchestrator.git")

_ALLOWED_MODULES = ("orchestrator", "orchestrator._package_exports")

_LAYERING_SCRIPT = """
import sys
import {module}
print(*sorted(name for name in sys.modules if name.startswith('orchestrator')))
"""

# The initializer binds nothing, so each name stays reachable only through its
# owner or the historical `verify` facade.
_OWNER_ONLY_NAMES = (
    "VerifyResult",
    "_VERIFY_OUTPUT_BUDGET",
    "_head_sha",
    "_worktree_dirty_files",
)

_FACADE_FORWARDS = (
    ("VerifyResult", models),
    ("_VERIFY_OUTPUT_BUDGET", models),
    ("_head_sha", probes),
    ("_worktree_dirty_files", probes),
)


def _imported_orchestrator_modules(module: str) -> list[str]:
    """Names of the orchestrator modules a fresh `import module` pulls in."""
    completed = subprocess.run(
        [sys.executable, "-c", _LAYERING_SCRIPT.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.split()


class CleanProcessImportTest(unittest.TestCase):
    """Each verification module imports standalone in a fresh interpreter.

    The verify leaves that still live beside the facade import both the
    package owners and the facade itself, so importing any one of them first
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


class LayeringTest(unittest.TestCase):
    """The owners import nothing from the workflow or application layers."""

    def test_owners_stay_in_the_git_domain(self) -> None:
        for module in ("orchestrator.git.verification.models", "orchestrator.git.verification.probes"):
            with self.subTest(module=module):
                for imported in _imported_orchestrator_modules(module):
                    self.assertTrue(
                        self._within_allowed_layers(imported),
                        f"{module} reaches above the git domain via {imported}",
                    )

    def _within_allowed_layers(self, imported: str) -> bool:
        if imported in _ALLOWED_MODULES:
            return True
        return any(
            imported == root or imported.startswith(f"{root}.")
            for root in _ALLOWED_ROOTS
        )


class PackageSurfaceTest(unittest.TestCase):
    """The initializer carries no bindings; `verify` forwards to owners."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(git.verification, owner_only_name)

    def test_facade_resolves_owner_objects(self) -> None:
        # The facade forwards rather than rebuilding, so code reaching a helper
        # through `verify` sees the owner's definition.
        for export_name, owner in _FACADE_FORWARDS:
            with self.subTest(name=export_name):
                self.assertIs(
                    getattr(verify, export_name),
                    getattr(owner, export_name),
                )


if __name__ == "__main__":
    unittest.main()
