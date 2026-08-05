# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, layering, and surface checks for the stages package."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from orchestrator import stages as _flat_stages
from orchestrator import workflow as _workflow
from orchestrator.stages import documenting as _documenting
from orchestrator.workflow import stages as _stages

_PACKAGE = "orchestrator.workflow.stages"

_FACADE = "orchestrator.workflow"

_IMPORTED_SCRIPT = """
import sys
import {module}
print(*sorted(name for name in sys.modules if name.startswith('orchestrator')))
"""

# One handler a stage that still has a forwarder answers for, so resolving it on
# both facades proves the historical route is still wired.
_PROBE_HANDLER = "_handle_documenting"


def _imported_orchestrator_modules(module: str) -> set[str]:
    """Names of the orchestrator modules a fresh `import module` plants."""
    completed = subprocess.run(
        [sys.executable, "-c", _IMPORTED_SCRIPT.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(completed.stdout.split())


class CleanProcessImportTest(unittest.TestCase):
    """The package imports standalone in a fresh interpreter.

    Importing it runs the workflow initializer above it first, and that
    initializer installs hooks whose targets import `orchestrator.workflow`
    back. A subprocess gives the package a clean `sys.modules` no other test
    has already populated, exposing an import-order cycle a facade-first suite
    run would mask.
    """

    def test_package_imports_standalone(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-c", f"import {_PACKAGE}"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)


class LayeringTest(unittest.TestCase):
    """The package costs the facade above it and nothing else."""

    def test_import_reaches_no_handler_or_subsystem(self) -> None:
        # This is where a stage arrives, so a binding in the initializer is the
        # cheapest mistake to make and the hardest to notice: one handler bound
        # here would drag its leaves -- and the worktree, GitHub, and analytics
        # subsystems they sit on -- into every import of the package, including
        # the ones that only want a different stage.
        self.assertEqual(
            _imported_orchestrator_modules(_PACKAGE),
            _imported_orchestrator_modules(_FACADE) | {_PACKAGE},
        )


class PackageSurfaceTest(unittest.TestCase):
    """The initializer is a package marker that owns no names."""

    def test_package_sits_under_the_workflow_facade(self) -> None:
        self.assertEqual(_stages.__name__, _PACKAGE)
        self.assertTrue(hasattr(_stages, "__path__"))
        initializer = Path(_stages.__file__)
        self.assertEqual(initializer.name, "__init__.py")
        self.assertEqual(initializer.parent.name, "stages")
        self.assertEqual(initializer.parent.parent.name, "workflow")

    def test_initializer_binds_only_submodules(self) -> None:
        # Importing an owner plants it in the package namespace, so a submodule
        # is the only thing allowed to appear here. A re-export beside it would
        # make the initializer a second identity for that owner and charge every
        # importer of one stage for the imports of all the others.
        for name, bound in _stages.__dict__.items():
            if name.startswith("__"):
                continue
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(bound, "__name__", None), f"{_PACKAGE}.{name}",
                )

    def test_flat_stage_package_stays_the_route(self) -> None:
        # A nested package carrying the flat one's name is the hazard this
        # destination introduces: `orchestrator.stages` has to stay the module
        # historical imports land on for every stage that still keeps a
        # forwarder there, answering with the same object the workflow facade
        # does now that the handler lives on an owner under this package.
        self.assertIsNot(_stages, _flat_stages)
        self.assertIs(
            getattr(_workflow, _PROBE_HANDLER),
            getattr(_documenting, _PROBE_HANDLER),
        )
        self.assertIs(_workflow.stages, _stages)
        self.assertIn("stages", _workflow.__dir__())


if __name__ == "__main__":
    unittest.main()
