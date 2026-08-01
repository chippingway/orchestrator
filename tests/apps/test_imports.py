# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, import cost, and forwarding checks for the entrypoints."""
from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module
from pathlib import Path


_ORCHESTRATOR = "orchestrator"

_PACKAGE = f"{_ORCHESTRATOR}.apps"

_BOOTSTRAP = f"{_PACKAGE}.bootstrap"

_APP = f"{_PACKAGE}.trajectory_dashboard"

# The declared inventory. A new app is a deliberate edit here and a paragraph
# in the package's own map, which is what the inventory check compares the
# directory against.
_MODULES = (_BOOTSTRAP, _APP)

# The launch path an operator's shell history already carries, kept beside the
# canonical one because both have to answer for the same page.
_LEGACY = f"{_ORCHESTRATOR}.trajectory_dashboard"

# What `import orchestrator` alone plants, so the cost check can hold the app
# to its own chain and nothing besides.
_ROOT_MODULES = (_ORCHESTRATOR, f"{_ORCHESTRATOR}._package_exports")

# The optional dependency group neither launch path may cost at import: it is
# what the function-local imports inside `main()` exist for.
_VIEWER_GROUP = ("pandas", "plotly", "streamlit")

_PROBE = """
import sys
import {module}
print(*sorted(sys.modules))
"""


def _planted(module: str) -> frozenset[str]:
    """Names of the modules a fresh `import module` leaves loaded."""
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
    )
    return frozenset(completed.stdout.split())


class AppInventoryTest(unittest.TestCase):
    """The declared apps are the ones on disk, and none is published above."""

    def test_declared_modules_are_the_ones_on_disk(self) -> None:
        directory = Path(import_module(_PACKAGE).__file__).parent
        found = tuple(sorted(
            module_path.stem
            for module_path in directory.glob("*.py")
            if module_path.stem != "__init__"
        ))
        self.assertEqual(found, tuple(sorted(
            module.rpartition(".")[2] for module in _MODULES
        )))

    def test_the_initializer_publishes_nothing(self) -> None:
        # An app is started by name, so nothing is re-exported above it: a
        # binding here would put one page's whole composition behind an import
        # of the package, which is what the entry function defers.
        initializer = import_module(_PACKAGE)
        self.assertNotIn("__all__", initializer.__dict__)
        for name, bound in initializer.__dict__.items():
            if name.startswith("__"):
                continue
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(bound, "__name__", ""), f"{_PACKAGE}.{name}",
                )


class AppImportCostTest(unittest.TestCase):
    """Naming a launch path costs the shim, never the page behind it."""

    def test_the_app_plants_only_its_own_chain(self) -> None:
        # Every owner the page composes is imported inside `main()`, because
        # under a script launch the repo root only reaches `sys.path` on the
        # line above the entry function. Holding the cost to the shim is what
        # keeps that ordering from being undone by a tidy-looking hoist.
        planted = _planted(_APP)
        self.assertEqual(
            tuple(sorted(
                name for name in planted
                if name.startswith(_ORCHESTRATOR)
            )),
            (*_ROOT_MODULES, _PACKAGE, _BOOTSTRAP, _APP),
        )

    def test_neither_path_costs_the_viewer_group(self) -> None:
        for module in (_APP, _LEGACY):
            planted = _planted(module)
            for dependency in _VIEWER_GROUP:
                with self.subTest(module=module, dependency=dependency):
                    self.assertNotIn(dependency, planted)


class LegacyForwardingTest(unittest.TestCase):
    """The historical launch path hands back the app's own entry point."""

    def test_the_facade_main_is_the_app_s_own(self) -> None:
        self.assertIs(import_module(_LEGACY).main, import_module(_APP).main)


if __name__ == "__main__":
    unittest.main()
