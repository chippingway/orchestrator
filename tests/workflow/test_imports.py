# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import checks and package surface for the workflow package."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from orchestrator import _workflow_export_manifest
from orchestrator import workflow as _workflow
from orchestrator.workflow import engine as _engine
from tests.reexport_test_support import lazy_targets, resolve_target

_MODULES = (
    "orchestrator.workflow",
    "orchestrator.workflow.engine",
)

# Manifest targets, so importing the facade must leave every one of them out of
# `sys.modules`: the dispatcher, the tick loop, the stage handlers, and the
# worktree and GitHub subsystems those reach.
_DEFERRED_MODULES = (
    "orchestrator._workflow_dispatch",
    "orchestrator._workflow_tick",
    "orchestrator.github",
    "orchestrator.stages",
    "orchestrator.workflow.engine",
    "orchestrator.worktrees",
)

_LAZINESS_PROBE = (
    "import sys;"
    "import orchestrator.workflow;"
    "print(' '.join(name for name in {names!r} if name in sys.modules))"
)

# One export per resolver branch: a stage handler the manifest reads off its
# leaf, and a whole module the manifest binds by name.
_PROBE_EXPORTS = ("_handle_ready", "contextlib")


class CleanProcessImportTest(unittest.TestCase):
    """The package and its engine subpackage each import standalone.

    The initializer installs hooks that resolve the export manifest, and the
    leaves those hooks reach import `orchestrator.workflow` back at call time.
    A subprocess per module gives each a clean `sys.modules` no other test has
    already populated, exposing an import-order cycle a package-first suite run
    would mask.
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

    def test_import_resolves_no_target(self) -> None:
        # The package boundary is where an accidental eager binding is cheapest
        # to add and hardest to notice: a submodule import in the initializer
        # would drag the whole stage tree into every `orchestrator.workflow`
        # import, which the flat suite could never observe.
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                _LAZINESS_PROBE.format(names=_DEFERRED_MODULES),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "")


class PackageSurfaceTest(unittest.TestCase):
    """The initializer is the facade; the engine subpackage binds nothing."""

    def test_facade_lives_in_the_package_initializer(self) -> None:
        # The manifest keys its resolver on `orchestrator.workflow` and the
        # `.pyi` surface is matched against that module's own path, so the
        # facade has to stay the initializer rather than sit in a leaf the
        # package re-exports.
        self.assertTrue(hasattr(_workflow, "__path__"))
        initializer = Path(_workflow.__file__)
        self.assertEqual(initializer.name, "__init__.py")
        self.assertEqual(initializer.parent.name, "workflow")
        self.assertTrue(initializer.with_suffix(".pyi").is_file())

    def test_engine_initializer_binds_nothing(self) -> None:
        bound = [
            name
            for name in _engine.__dict__
            if not name.startswith("__")
        ]
        self.assertEqual(bound, [])

    def test_submodule_keeps_lazy_hooks(self) -> None:
        # Importing a submodule plants it in the package namespace the hooks
        # cache resolved exports into, so the two share one dict.
        self.assertIs(_workflow.engine, _engine)
        targets = lazy_targets(_workflow_export_manifest)
        for export_name in _PROBE_EXPORTS:
            with self.subTest(name=export_name):
                resolved = resolve_target(
                    _workflow, export_name, targets[export_name],
                )
                self.assertIs(resolved.direct, resolved.expected)
                self.assertIs(resolved.imported, resolved.expected)
        self.assertEqual(
            _workflow.__all__, _workflow_export_manifest.EXPORTED_NAMES,
        )
        self.assertIn("engine", _workflow.__dir__())


if __name__ == "__main__":
    unittest.main()
