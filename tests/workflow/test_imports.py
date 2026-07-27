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
from orchestrator.workflow.engine import (
    comments as _comments,
    drift as _drift,
    messages as _messages,
    prompts as _prompts,
    usage as _usage,
)
from tests.reexport_test_support import lazy_targets, resolve_target

_MODULES = (
    "orchestrator.workflow",
    "orchestrator.workflow.engine",
    "orchestrator.workflow.engine.comments",
    "orchestrator.workflow.engine.drift",
    "orchestrator.workflow.engine.messages",
    "orchestrator.workflow.engine.prompts",
    "orchestrator.workflow.engine.usage",
    "orchestrator.workflow.state",
)

# Manifest targets and what they resolve to, so importing the facade must leave
# every one of them out of `sys.modules`: the dispatcher, the tick loop, the
# stage handlers, the worktree and GitHub subsystems those reach, and the
# analytics and config packages behind the shared dependency bindings.
_DEFERRED_MODULES = (
    "orchestrator._workflow_dispatch",
    "orchestrator._workflow_tick",
    "orchestrator.analytics",
    "orchestrator.config",
    "orchestrator.github",
    "orchestrator.stages",
    "orchestrator.workflow.engine",
    "orchestrator.worktrees",
)

# The `state` owner is what the GitHub and git layers below the engine are typed
# by, so an import of it has to cost no more than the initializer it runs.
_LAZY_IMPORTS = (
    "orchestrator.workflow",
    "orchestrator.workflow.state",
)

_LAZINESS_PROBE = (
    "import sys;"
    "import {module};"
    "print(' '.join(name for name in {names!r} if name in sys.modules))"
)

# One export per resolver branch: a stage handler the manifest reads off its
# leaf, and a whole module the manifest binds by name.
_PROBE_EXPORTS = ("_handle_ready", "contextlib")


class CleanProcessImportTest(unittest.TestCase):
    """The package, its subpackage, and each owner beneath them import alone.

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
        # to add and hardest to notice: a submodule or dependency import in the
        # initializer would drag the stage tree or the analytics graph into every
        # `orchestrator.workflow` import -- and into the GitHub and git layers
        # that import the state owner beside it -- which the flat suite could
        # never observe.
        for module in _LAZY_IMPORTS:
            with self.subTest(module=module):
                self._assert_nothing_resolved(module)

    def _assert_nothing_resolved(self, module: str) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                _LAZINESS_PROBE.format(
                    module=module, names=_DEFERRED_MODULES,
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "")


class PackageSurfaceTest(unittest.TestCase):
    """The initializer is the facade; the engine subpackage owns no names."""

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
        # Importing an owner plants it in the package namespace, so a submodule
        # is the only thing allowed to appear here. A re-export beside it would
        # make the initializer a second identity for that owner and charge every
        # importer of one owner for the imports of all the others.
        self.assertIs(_engine.comments, _comments)
        self.assertIs(_engine.drift, _drift)
        self.assertIs(_engine.messages, _messages)
        self.assertIs(_engine.prompts, _prompts)
        self.assertIs(_engine.usage, _usage)
        for name, bound in _engine.__dict__.items():
            if name.startswith("__"):
                continue
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(bound, "__name__", None), f"{_engine.__name__}.{name}",
                )

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
