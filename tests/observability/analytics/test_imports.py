# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, surface, and layering checks for the analytics owners."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path

from orchestrator.observability import analytics as _package
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
)

_PACKAGE = "orchestrator.observability.analytics"

_CONFIG_OWNER = "config"

# The declared inventory. A new owner is a deliberate edit here and a
# paragraph in the module map, which is what the inventory check compares the
# directory against.
_OWNERS = (_CONFIG_OWNER,)

# What the configuration owner answers for: the six knobs, the whole set under
# the names the analytics package publishes them as, the view every adapter
# reads one back through and the two ways it is entered, and the read-path URL
# fallback.
_CONFIG_SURFACE = (
    "Settings",
    "live_settings",
    "parse_db_url",
    "parse_log_path",
    "parse_retention_days",
    "parse_track_skill_triggers",
    "parse_trajectory_log_path",
    "parse_trajectory_retention_days",
    "parsed_settings",
    "resolve_db_url",
    "settings_on",
)

# The flat leaves whose responsibility this owner took over. Either left
# behind would be a second place a knob could be parsed from.
_VACATED_LEAVES = (
    "orchestrator/analytics/_recording_settings.py",
    "orchestrator/analytics/db_url.py",
)

# Every adapter that has to obtain configuration from the owner: the package
# bootstrap that binds the parsed knobs, the append and prune paths of both
# sinks, the two skill readers that take their holder off an exit context, the
# two read-path modules that resolve a query's URL, and the sync request that
# falls back to both sink knobs.
_ADAPTERS = (
    "orchestrator.analytics._package_initialization",
    "orchestrator.analytics._recording",
    "orchestrator.analytics._recording_catalog",
    "orchestrator.analytics._recording_skills",
    "orchestrator.analytics._retention",
    "orchestrator.analytics._trajectories",
    "orchestrator.analytics._trajectory_persistence",
    "orchestrator.analytics.connection",
    "orchestrator.analytics.query",
    "orchestrator.analytics._sync_run",
)


def _qualified(owner: str) -> str:
    return f"{_PACKAGE}.{owner}"


def _defined_here(owner: str) -> tuple[str, ...]:
    """Public names the owner defines, as opposed to ones it imported."""
    module = import_module(_qualified(owner))
    return tuple(sorted(
        name
        for name, member in module.__dict__.items()
        if not name.startswith("_")
        and getattr(member, "__module__", None) == module.__name__
    ))


class OwnerInventoryTest(unittest.TestCase):
    """The declared owners are the ones on disk, and nothing is left behind."""

    def test_declared_owners_are_the_ones_on_disk(self) -> None:
        directory = Path(_package.__file__).parent
        found = tuple(sorted(
            module_path.stem
            for module_path in directory.glob("*.py")
            if module_path.stem != "__init__"
        ))
        self.assertEqual(found, tuple(sorted(_OWNERS)))

    def test_no_vacated_leaf_survives(self) -> None:
        repository_root = Path(import_module("orchestrator").__file__).parents[1]
        for leaf in _VACATED_LEAVES:
            with self.subTest(leaf=leaf):
                self.assertFalse(repository_root.joinpath(leaf).exists())


class PublicSurfaceTest(unittest.TestCase):
    """The configuration owner answers for a narrow, declared surface."""

    def test_public_names_are_the_declared_ones(self) -> None:
        # Declared rather than discovered, so a new public name here is a
        # deliberate edit: this owner is what a caller reaches for a setting,
        # and an accidental export is a second answer to the same question.
        self.assertEqual(_defined_here(_CONFIG_OWNER), _CONFIG_SURFACE)

    def test_no_surface_is_declared_twice(self) -> None:
        # The package initializer is a marker, so a name is reached on the
        # owner that defines it rather than published a second time above it.
        owner = import_module(_qualified(_CONFIG_OWNER))
        self.assertNotIn("__all__", owner.__dict__)
        self.assertNotIn("__all__", _package.__dict__)


class LayeringTest(unittest.TestCase):
    """The owner reaches nothing outside, and every adapter names it."""

    def test_no_owner_reaches_outside_the_package(self) -> None:
        # The sharpest case this rejects is the analytics package itself: the
        # owner is imported from inside it and reads the live settings back
        # off it, so binding that import at module scope would cycle and make
        # the compatibility package load-bearing rather than retirable.
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            for imported in planted:
                with self.subTest(owner=owner, imported=imported):
                    self.assertTrue(
                        imported.startswith("orchestrator.observability")
                        or imported.startswith("orchestrator._package")
                        or imported == "orchestrator",
                        f"{owner} reaches {imported}",
                    )

    def test_every_adapter_names_the_owner(self) -> None:
        # Configuration has one source, so an adapter that parses a knob or
        # re-reads the environment itself would be a second one.
        for adapter in _ADAPTERS:
            with self.subTest(adapter=adapter):
                self.assertIn(
                    _qualified(_CONFIG_OWNER),
                    _imported_orchestrator_modules(adapter),
                )


if __name__ == "__main__":
    unittest.main()
