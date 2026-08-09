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

_ANALYTICS_APP = f"{_PACKAGE}.analytics_dashboard"

_TRAJECTORY_APP = f"{_PACKAGE}.trajectory_dashboard"

_APPS = (_ANALYTICS_APP, _TRAJECTORY_APP)

# The declared inventory. A new app is a deliberate edit here and a paragraph
# in the package's own map, which is what the inventory check compares the
# directory against.
_MODULES = (_BOOTSTRAP, *_APPS)

# The app paired with the launch path an operator's shell history already
# carries, kept beside it because both have to answer for the same page.
_LAUNCH_PAIRS = (
    (_TRAJECTORY_APP, f"{_ORCHESTRATOR}.trajectory_dashboard"),
)

# What `import orchestrator` alone plants, so the cost check can hold each app
# to its own chain and nothing besides.
_ROOT_MODULES = (_ORCHESTRATOR, f"{_ORCHESTRATOR}._package_exports")

# The optional dependency group no launch path may cost at import: it is what
# the function-local imports inside the page's passes exist for.
_DASHBOARD_GROUP = ("pandas", "plotly", "streamlit")

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

    def test_each_app_plants_only_its_own_chain(self) -> None:
        # Every owner a page composes is imported inside the pass that reaches
        # it, because under a script launch the repo root only reaches
        # `sys.path` on the line above them. Holding the cost to the shim is
        # what keeps that ordering from being undone by a tidy-looking hoist.
        for app in _APPS:
            with self.subTest(app=app):
                planted = _planted(app)
                self.assertEqual(
                    tuple(sorted(
                        name for name in planted
                        if name.startswith(_ORCHESTRATOR)
                    )),
                    tuple(sorted((*_ROOT_MODULES, _PACKAGE, _BOOTSTRAP, app))),
                )

    def test_no_path_costs_the_dashboard_group(self) -> None:
        for module in (*_APPS, *(legacy for _, legacy in _LAUNCH_PAIRS)):
            planted = _planted(module)
            for dependency in _DASHBOARD_GROUP:
                with self.subTest(module=module, dependency=dependency):
                    self.assertNotIn(dependency, planted)


class LegacyForwardingTest(unittest.TestCase):
    """The historical launch path hands back the app's own composition."""

    def test_each_facade_main_is_its_app_s_own(self) -> None:
        for app, legacy in _LAUNCH_PAIRS:
            with self.subTest(app=app):
                self.assertIs(
                    import_module(legacy).main, import_module(app).main,
                )


if __name__ == "__main__":
    unittest.main()
