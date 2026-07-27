# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, layering, and surface checks for the stage package."""

from __future__ import annotations

import importlib
import subprocess
import sys
import unittest
from pathlib import Path
from types import MappingProxyType

from orchestrator import _workflow_export_manifest
from orchestrator import workflow as _workflow
from orchestrator.stages import (
    _validating_export_manifest as _forwarder_manifest,
    validating as _forwarder,
)
from orchestrator.workflow.engine import dispatch as _dispatch
from orchestrator.workflow.stages import validating as _package

_PACKAGE = "orchestrator.workflow.stages.validating"

_PARENT = "orchestrator.workflow.stages"

_HANDLER_OWNER = "handler"

_OWNERS = (
    "approval",
    "awaiting",
    "awaiting_resume",
    "dev_fix",
    "drift",
    "drift_outcomes",
    _HANDLER_OWNER,
    "models",
    "recovery",
    "requested_changes",
    "reviewer",
    "state",
    "verify",
    "watermarks",
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

_HANDLE_VALIDATING = "_handle_validating"


def _imported_orchestrator_modules(module: str) -> set[str]:
    """Names of the orchestrator modules a fresh `import module` plants."""
    completed = subprocess.run(
        [sys.executable, "-c", _IMPORTED_SCRIPT.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(completed.stdout.split())


def _package_targets(manifest) -> list:
    """Every manifest entry this package owns."""
    return [
        target for target in manifest.EXPORTS
        if target.module_name.startswith(_PACKAGE)
    ]


class CleanProcessImportTest(unittest.TestCase):
    """The package and each owner beneath it import alone.

    The owners import each other and reach the engine and the verification
    runner, which reach the workflow facade, whose hooks resolve back into this
    package. A subprocess per module gives each a clean `sys.modules` no other
    test has already populated, exposing an import-order cycle a facade-first
    suite run would mask.
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
        # An eager owner binding here would charge a park or a watermark walk
        # for the reviewer spawn it never reaches -- and for the worktree,
        # GitHub, verification, and analytics subsystems those sit on.
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
        self.assertEqual(initializer.parent.name, "validating")
        self.assertIs(importlib.import_module(_PARENT).validating, _package)

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

    def test_no_flat_leaf_is_left_behind(self) -> None:
        # The migration is only finished when every historical name resolves
        # off an owner here; a `_validating_*` target left in the inventory
        # would be a leaf the flat package still owns.
        for target in _forwarder_manifest.EXPORTS:
            with self.subTest(name=target.export_name):
                self.assertNotIn("_validating_", target.module_name)


class ForwardedSurfaceTest(unittest.TestCase):
    """Both historical import sites hand back the owner's own objects."""

    def test_flat_facade_forwards_owner_names(self) -> None:
        for target in _package_targets(_forwarder_manifest):
            with self.subTest(name=target.export_name):
                owner = _OWNER_MODULES[target.module_name.rsplit(".", 1)[1]]
                self.assertIs(
                    getattr(_forwarder, target.export_name),
                    getattr(owner, target.target_name),
                )

    def test_workflow_facade_forwards_owner_names(self) -> None:
        for target in _package_targets(_workflow_export_manifest):
            with self.subTest(name=target.export_name):
                owner = _OWNER_MODULES[target.module_name.rsplit(".", 1)[1]]
                self.assertIs(
                    getattr(_workflow, target.export_name),
                    getattr(owner, target.target_name),
                )


class DispatchTargetTest(unittest.TestCase):
    """The dispatcher names the handler owner."""

    def test_label_resolves_to_the_handler_owner(self) -> None:
        # The stage keeps answering through the forwarder it left behind, but a
        # dispatched handler is resolved off the module the table names -- so
        # that is where a patch has to land to intercept one.
        owner = _OWNER_MODULES[_HANDLER_OWNER]
        self.assertEqual(
            _dispatch._STAGE_HANDLER_TARGETS["validating"],
            (owner.__name__, _HANDLE_VALIDATING),
        )
        self.assertTrue(hasattr(owner, _HANDLE_VALIDATING))


if __name__ == "__main__":
    unittest.main()
