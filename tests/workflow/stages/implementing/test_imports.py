# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, layering, and surface checks for the stage package."""

from __future__ import annotations

import importlib
import subprocess
import sys
import unittest
from importlib.util import find_spec
from pathlib import Path
from types import MappingProxyType

from orchestrator import _workflow_export_manifest
from orchestrator import workflow as _workflow
from orchestrator.workflow.engine import dispatch as _dispatch, pickup as _pickup
from orchestrator.workflow.stages import implementing as _package

_PACKAGE = "orchestrator.workflow.stages.implementing"

_PARENT = "orchestrator.workflow.stages"

_HANDLER_OWNER = "handler"

_OWNERS = (
    "continue_command",
    "disposition",
    "drift",
    "drift_preflight",
    "execution",
    _HANDLER_OWNER,
    "models",
    "parks",
    "publication",
    "question_relabel",
    "resume",
    "session",
    "session_read",
    "spawn",
    "state",
    "worktree",
)

# Bound at module scope, so collecting this file is what plants every owner in
# `sys.modules` -- the same protection each sibling owner package gets from its
# own import test, and what keeps an owner from being first imported by a test
# that has already reloaded the modules it binds.
_OWNER_MODULES = MappingProxyType({
    owner: importlib.import_module(f"{_PACKAGE}.{owner}") for owner in _OWNERS
})

_IMPORTED_SCRIPT = """
import sys
import {module}
print(*sorted(name for name in sys.modules if name.startswith('orchestrator')))
"""

_HANDLE_IMPLEMENTING = "_handle_implementing"

# The module paths a second import site for these owners would take: the flat
# spelling itself, and the inventory and resolver hooks one would be built from.
_FLAT_MODULES = (
    "orchestrator.stages._implementing_export_manifest",
    "orchestrator.stages._implementing_exports",
    "orchestrator.stages.implementing",
)


def _imported_orchestrator_modules(module: str) -> set[str]:
    """Names of the orchestrator modules a fresh `import module` plants."""
    completed = subprocess.run(
        [sys.executable, "-c", _IMPORTED_SCRIPT.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(completed.stdout.split())


def _stage_targets() -> list:
    """Every workflow-manifest entry that names this stage."""
    return [
        target for target in _workflow_export_manifest.EXPORTS
        if "implementing" in target.module_name
    ]


class CleanProcessImportTest(unittest.TestCase):
    """The package and each owner beneath it import alone.

    The owners import each other and reach the engine, which reaches the
    workflow facade, whose hooks resolve back into this package. A subprocess
    per module gives each a clean `sys.modules` no other test has already
    populated, exposing an import-order cycle a facade-first suite run would
    mask.
    """

    def test_each_module_imports_standalone(self) -> None:
        for module in (_PACKAGE, *(f"{_PACKAGE}.{owner}" for owner in _OWNERS)):
            with self.subTest(module=module):
                completed = subprocess.run(
                    [sys.executable, "-c", f"import {module}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)


class LayeringTest(unittest.TestCase):
    """The initializer costs the package above it and nothing else."""

    def test_initializer_reaches_no_owner(self) -> None:
        # An eager owner binding here would charge a park or a session read for
        # the publication path it never reaches -- and for the worktree, GitHub,
        # and analytics subsystems those sit on.
        self.assertEqual(
            _imported_orchestrator_modules(_PACKAGE),
            _imported_orchestrator_modules(_PARENT) | {_PACKAGE},
        )


class PackageSurfaceTest(unittest.TestCase):
    """The initializer is a package marker that owns no names."""

    def test_package_sits_under_the_stage_package(self) -> None:
        self.assertEqual(_package.__name__, _PACKAGE)
        initializer = Path(_package.__file__)
        self.assertEqual(initializer.name, "__init__.py")
        self.assertEqual(initializer.parent.name, "implementing")
        self.assertIs(importlib.import_module(_PARENT).implementing, _package)

    def test_initializer_binds_only_submodules(self) -> None:
        for owner, module in _OWNER_MODULES.items():
            with self.subTest(owner=owner):
                self.assertIs(getattr(_package, owner), module)
        for name, bound in _package.__dict__.items():
            if name.startswith("__"):
                continue
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(bound, "__name__", None), f"{_PACKAGE}.{name}",
                )


class OwnerImportSiteTest(unittest.TestCase):
    """The owners here are the only modules this stage's names answer on."""

    def test_no_flat_module_exists(self) -> None:
        # Anything importable at these paths would be a second identity for the
        # dev-session keys, the retry budget, and the park reasons live issues
        # are already carrying, free to drift from the owner silently and
        # invisible to a patch aimed at it. Resolving the spec rather than
        # stat-ing one path catches a copy planted anywhere the interpreter
        # would find it.
        for module in _FLAT_MODULES:
            with self.subTest(module=module):
                self.assertIsNone(find_spec(module))

    def test_facade_reads_every_name_off_an_owner(self) -> None:
        # The facade is the inventory historical callers and patches still
        # reach this stage through, so each name it publishes has to be an
        # owner's own object rather than one rebuilt beside them.
        for target in _stage_targets():
            with self.subTest(name=target.export_name):
                owner_package, _, owner = target.module_name.rpartition(".")
                self.assertEqual(owner_package, _PACKAGE)
                self.assertIs(
                    getattr(_workflow, target.export_name),
                    getattr(_OWNER_MODULES[owner], target.target_name),
                )


class DispatchTargetTest(unittest.TestCase):
    """The dispatcher and the pickup start name the handler owner."""

    def test_label_resolves_to_the_handler_owner(self) -> None:
        # A dispatched handler is resolved off the module the table names, so
        # that is where a patch has to land to intercept one.
        owner = _OWNER_MODULES[_HANDLER_OWNER]
        self.assertEqual(
            _dispatch._STAGE_HANDLER_TARGETS["implementing"],
            (owner.__name__, _HANDLE_IMPLEMENTING),
        )
        self.assertTrue(hasattr(owner, _HANDLE_IMPLEMENTING))

    def test_decompose_off_start_names_the_owner(self) -> None:
        # `DECOMPOSE=off` dispatches the handler inside the pickup tick, so the
        # legacy start reads it off the owner for the same reason.
        source = Path(_pickup.__file__).read_text(encoding="utf-8")
        self.assertIn(
            f"from {_PACKAGE}.{_HANDLER_OWNER} import {_HANDLE_IMPLEMENTING}", source,
        )


if __name__ == "__main__":
    unittest.main()
