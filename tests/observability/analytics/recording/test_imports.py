# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, surface, and layering checks for the recording owners."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from orchestrator.observability.analytics import recording as _package
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
    _under,
)


_PACKAGE = "orchestrator.observability.analytics.recording"

# The owner every recorder and the sink append are defined on.
_EVENTS_OWNER = "events"

# The declared inventory. A new owner is a deliberate edit here and a
# paragraph in the module map, which is what the inventory check compares the
# directory against.
_OWNERS = (
    "agent_exit",
    "catalog",
    _EVENTS_OWNER,
    "io",
    "models",
    "skills",
    "usage",
)

# Bound at module scope, so collecting this file is what plants every owner in
# `sys.modules` rather than whichever recorder test happened to run first.
_OWNER_MODULES = MappingProxyType({
    owner: import_module(f"{_PACKAGE}.{owner}") for owner in _OWNERS
})

# What the package publishes: the envelope and the append under it, plus one
# recorder per producer-facing event family.
_PUBLISHED = (
    "append_record",
    "build_record",
    "record_agent_exit",
    "record_repo_skill_catalog",
    "record_stage_enter",
    "record_stage_evaluation",
)

# The flat leaves whose responsibility these owners took over. Any survivor
# would be a second place a record could be built or a sink line written.
_VACATED_LEAVES = (
    "orchestrator/analytics/_recording.py",
    "orchestrator/analytics/_recording_agent_exit.py",
    "orchestrator/analytics/_recording_catalog.py",
    "orchestrator/analytics/_recording_dependencies.py",
    "orchestrator/analytics/_recording_io.py",
    "orchestrator/analytics/_recording_models.py",
    "orchestrator/analytics/_recording_skills.py",
    "orchestrator/analytics/_recording_usage.py",
)

# Every module that appends an analytics record, paired with nothing else it
# needs: the client's paired audit / analytics stage-enter hook, the dispatch
# that times one handler, the tracked agent run, and the per-tick skill
# catalog. Each is checked to reach the owner *and* not the flat analytics
# package -- the settings still live there, but they are resolved inside the
# call, which is what makes that package retirable rather than load-bearing.
_PRODUCERS = (
    "orchestrator.github.client",
    "orchestrator.workflow.engine.dispatch",
    "orchestrator.workflow.engine.usage",
    "orchestrator.skills.catalog",
)

_ANALYTICS_PACKAGE = "orchestrator.analytics"

# What an owner here is allowed to reach: its siblings, the configuration
# owner every knob is read through, the parsers a finished run is metered by,
# and the trajectory writers an `agent_exit` hands that run's second record to.
# The query, sync, and page graphs are deliberately absent -- this is the one
# analytics path the orchestrator process itself runs.
_REACHABLE = (
    _PACKAGE,
    "orchestrator.observability.analytics.config",
    "orchestrator.observability.analytics.trajectories",
    "orchestrator.observability.usage",
    "orchestrator.observability",
    "orchestrator._package",
    "orchestrator",
)


def _qualified(owner: str) -> str:
    return f"{_PACKAGE}.{owner}"


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
    """The package publishes a narrow, accurate `__all__`."""

    def test_published_surface_is_the_declared_one(self) -> None:
        # Declared rather than discovered, so a new public name here is a
        # deliberate edit: this package is what a producer reaches to append a
        # record, and an accidental export is a second way to write one.
        self.assertEqual(_package.__all__, _PUBLISHED)
        self.assertEqual(_package.__all__, tuple(sorted(_package.__all__)))

    def test_published_names_are_the_owner_s_objects(self) -> None:
        # The package publishes the owner's own object rather than a wrapper
        # around it, so the module a name reports is the module that defines
        # it -- which is where a reader looks for the source.
        owner = _OWNER_MODULES[_EVENTS_OWNER]
        for name in _PUBLISHED:
            with self.subTest(name=name):
                self.assertIs(getattr(_package, name), getattr(owner, name))
                self.assertEqual(
                    getattr(owner, name).__module__, _qualified(_EVENTS_OWNER),
                )

    def test_no_owner_declares_a_surface_of_its_own(self) -> None:
        # One `__all__` for the package, so a name cannot be published here
        # and forgotten there.
        for owner, module in _OWNER_MODULES.items():
            with self.subTest(owner=owner):
                self.assertNotIn("__all__", module.__dict__)


class LayeringTest(unittest.TestCase):
    """The owners reach only what they compose, and every producer names them."""

    def test_no_owner_reaches_past_what_it_composes(self) -> None:
        # The sharpest case this rejects is the flat analytics package: the
        # recorders read their settings off it and dispatch through it, so
        # binding that import would cycle and make the compatibility package
        # load-bearing rather than retirable.
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            for imported in planted:
                with self.subTest(owner=owner, imported=imported):
                    self.assertTrue(
                        _under(imported, _REACHABLE),
                        f"{owner} reaches {imported}",
                    )

    def test_every_producer_names_the_owner(self) -> None:
        for producer in _PRODUCERS:
            planted = _imported_orchestrator_modules(producer)
            with self.subTest(producer=producer):
                self.assertIn(_PACKAGE, planted)
                self.assertNotIn(_ANALYTICS_PACKAGE, planted)


if __name__ == "__main__":
    unittest.main()
