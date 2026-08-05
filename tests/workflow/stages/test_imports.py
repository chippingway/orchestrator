# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, layering, and surface checks for the stages package."""

from __future__ import annotations

import importlib
import pkgutil
import subprocess
import sys
import unittest
from importlib.util import find_spec
from pathlib import Path

from orchestrator import workflow as _workflow
from orchestrator.workflow import stages as _stages
from orchestrator.workflow.engine import dispatch as _dispatch

_PACKAGE = "orchestrator.workflow.stages"

_FACADE = "orchestrator.workflow"

# The flat spelling a second import site for any of these stages would take.
_FLAT_PACKAGE = "orchestrator.stages"

_IMPORTED_SCRIPT = """
import sys
import {module}
print(*sorted(name for name in sys.modules if name.startswith('orchestrator')))
"""

# One handler and the owner it lives on, so resolving it on the facade proves
# the historical route into a stage is still wired.
_PROBE_HANDLER = "_handle_fixing"

_PROBE_OWNER = f"{_PACKAGE}.fixing.handler"


def _imported_orchestrator_modules(module: str) -> set[str]:
    """Names of the orchestrator modules a fresh `import module` plants."""
    completed = subprocess.run(
        [sys.executable, "-c", _IMPORTED_SCRIPT.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(completed.stdout.split())


def _stage_packages() -> list[str]:
    """Every stage subpackage that lives under this package."""
    return [found.name for found in pkgutil.iter_modules(_stages.__path__)]


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

    def test_facade_reaches_the_handler_owner(self) -> None:
        # The workflow facade is the route a historical caller and its patches
        # take to a handler, so it has to keep answering with the object the
        # owner under this package holds rather than one rebuilt beside it.
        self.assertIs(
            getattr(_workflow, _PROBE_HANDLER),
            getattr(importlib.import_module(_PROBE_OWNER), _PROBE_HANDLER),
        )
        self.assertIs(_workflow.stages, _stages)
        self.assertIn("stages", _workflow.__dir__())


class OwnerTreeImportSiteTest(unittest.TestCase):
    """The owners under this package are where every stage answers."""

    def test_no_flat_stage_package_resolves(self) -> None:
        # A package at this spelling would be a second import site for stages
        # whose owners live here, free to drift from them silently and
        # invisible to a patch aimed at one. Resolving the spec rather than
        # stat-ing a path is what makes this "nothing the interpreter would
        # find", covering a directory with no initializer -- still importable
        # as a namespace package -- as well as one carrying a module.
        self.assertIsNone(find_spec(_FLAT_PACKAGE))

    def test_every_label_dispatches_to_an_owner_here(self) -> None:
        # A handler resolved off a module outside this tree would be a second
        # identity for the stage, and a patch on the owner would not intercept
        # the dispatched call. The unlabeled entry is skipped because an
        # unlabeled issue starts on the engine's pickup sibling, not a stage.
        stage_packages = {f"{_PACKAGE}.{stage}" for stage in _stage_packages()}
        for label, (module_name, _) in _dispatch._STAGE_HANDLER_TARGETS.items():
            if label is None:
                continue
            with self.subTest(label=label):
                self.assertIn(module_name.rpartition(".")[0], stage_packages)


if __name__ == "__main__":
    unittest.main()
