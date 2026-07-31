# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, layering, and forwarding checks for the usage owners."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from orchestrator import usage as _facade
from orchestrator.observability import usage as _package
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
)


_PACKAGE = "orchestrator.observability.usage"

_FACADE = "orchestrator.usage"

# The owner every agent result and the per-issue meter is typed by.
_METRICS_OWNER = "metrics"

# The declared inventory. A new owner is a deliberate edit here and a
# paragraph in the module map, which is what the inventory check compares the
# directory against.
_OWNERS = (
    "claude_rows",
    "claude_summary",
    "codex_rows",
    "codex_summary",
    "event_stream",
    _METRICS_OWNER,
    "model_names",
    "prices",
    "protocol",
    "shell_segments",
    "skill_commands",
    "skills",
    "skills_claude",
    "skills_codex",
    "trajectory",
    "trajectory_claude_blocks",
    "trajectory_claude_stream",
    "trajectory_claude_turns",
    "trajectory_codex",
    "trajectory_models",
)

# Bound at module scope, so collecting this file is what plants every owner in
# `sys.modules` rather than whichever parser test happened to run first.
_OWNER_MODULES = MappingProxyType({
    owner: import_module(f"{_PACKAGE}.{owner}") for owner in _OWNERS
})

# What the package publishes, grouped by the owner each name is defined on --
# and, taken together, the whole surface the compatibility site forwards.
_PUBLISHED = MappingProxyType({
    _METRICS_OWNER: (
        "UsageMetrics",
        "parse_agent_usage",
        "parse_claude_usage",
        "parse_codex_usage",
    ),
    "skills": (
        "SkillTriggers",
        "parse_agent_skills",
        "parse_claude_skills",
        "parse_codex_skills",
    ),
    "trajectory": (
        "parse_agent_trajectory",
        "parse_claude_trajectory",
        "parse_codex_trajectory",
    ),
})

# Three of the five result types are defined off an entry point, on the module
# the trajectory parsers build them from; the other two sit beside the parser
# that fills each and are grouped with it above.
_RECORD_OWNER = "trajectory_models"

_RECORDS = ("AgentTrajectory", "TrajectoryStep", "TurnUsage")

# Every module that meters a finished run, paired with the owner it has to
# have imported to do so: the agent result `UsageMetrics` types, the tracked
# run that folds the counters, and the two analytics writers -- the token /
# cost record on one side and the opt-in trajectory record on the other.
_CALLERS = (
    ("orchestrator.agents.models", _METRICS_OWNER),
    ("orchestrator.workflow.engine.usage", _METRICS_OWNER),
    ("orchestrator.observability.analytics.recording.usage", _METRICS_OWNER),
    ("orchestrator.observability.analytics.recording.skills", "skills"),
    ("orchestrator.observability.analytics.trajectories.persistence", "trajectory"),
    ("orchestrator.observability.analytics.trajectories.serialize", _RECORD_OWNER),
)

# `from __future__ import annotations` binds its own feature flag, which is
# not something the facade forwards.
_FUTURE_FEATURE = "annotations"


def _qualified(owner: str) -> str:
    return f"{_PACKAGE}.{owner}"


class OwnerInventoryTest(unittest.TestCase):
    """The declared owners are the ones on disk."""

    def test_declared_owners_are_the_ones_on_disk(self) -> None:
        directory = Path(_package.__file__).parent
        found = tuple(sorted(
            module_path.stem
            for module_path in directory.glob("*.py")
            if module_path.stem != "__init__"
        ))
        self.assertEqual(found, tuple(sorted(_OWNERS)))

    def test_no_flat_leaf_is_left_behind(self) -> None:
        # The migration is only finished when every parser resolves off an
        # owner here; a `_usage_*` leaf beside the facade would be one the
        # flat package still owns.
        package_root = Path(import_module("orchestrator").__file__).parent
        self.assertEqual(list(package_root.glob("_usage_*.py")), [])


class PublicSurfaceTest(unittest.TestCase):
    """The package publishes a narrow, accurate `__all__`."""

    def test_published_surface_is_the_declared_one(self) -> None:
        declared = set(_RECORDS)
        for published in _PUBLISHED.values():
            declared.update(published)
        self.assertEqual(set(_package.__all__), declared)
        self.assertEqual(_package.__all__, tuple(sorted(_package.__all__)))

    def test_published_names_are_the_owners_objects(self) -> None:
        # The package publishes the owner's own object rather than a wrapper
        # around it, so the module a name reports is the module that defines
        # it. The binding is made once, at import: it is the identity that is
        # shared, not a later rebinding, which is why a test intercepting a
        # parser patches the module its caller imported.
        for owner, published in _PUBLISHED.items():
            module = _OWNER_MODULES[owner]
            for name in published:
                with self.subTest(owner=owner, name=name):
                    self.assertIs(getattr(_package, name), getattr(module, name))
                    self.assertEqual(
                        getattr(module, name).__module__, _qualified(owner),
                    )

    def test_records_come_from_their_owner(self) -> None:
        # The trajectory records are published beside the parsers that return
        # them even though the module defining them is not an entry point.
        owner = _OWNER_MODULES[_RECORD_OWNER]
        for name in _RECORDS:
            with self.subTest(name=name):
                self.assertIs(getattr(_package, name), getattr(owner, name))

    def test_no_owner_declares_a_surface_of_its_own(self) -> None:
        # One `__all__` for the package, so a name cannot be published here
        # and forgotten there.
        for owner, module in _OWNER_MODULES.items():
            with self.subTest(owner=owner):
                self.assertNotIn("__all__", module.__dict__)

    def test_records_report_their_defining_module(self) -> None:
        # The records carry a hand-built `__init__` and signature, so a
        # relocated `__module__` would point a reader at a module whose source
        # does not contain them.
        owner = _OWNER_MODULES[_RECORD_OWNER]
        for name in _RECORDS:
            with self.subTest(name=name):
                self.assertEqual(
                    getattr(owner, name).__module__, _qualified(_RECORD_OWNER),
                )


class LayeringTest(unittest.TestCase):
    """The owners reach nothing outside, and no caller reaches the facade."""

    def test_no_owner_reaches_outside_the_package(self) -> None:
        # The sharpest case this rejects is the compatibility site: it imports
        # the owners, so an owner reading it back would both cycle and make
        # the temporary module load-bearing rather than deletable.
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

    def test_no_caller_pulls_the_facade_in(self) -> None:
        # Every module that meters a run names an owner, so nothing on the
        # tick path imports the compatibility site. That is what makes it
        # deletable: while one live caller still reaches it, the module is
        # load-bearing on every import of the analytics or workflow layer.
        for caller, owner in _CALLERS:
            planted = _imported_orchestrator_modules(caller)
            with self.subTest(caller=caller):
                self.assertIn(_qualified(owner), planted)
                self.assertNotIn(_FACADE, planted)


class ForwardedSurfaceTest(unittest.TestCase):
    """The facade hands back the owners' own objects."""

    def test_entry_points_are_forwarded(self) -> None:
        for owner, published in _PUBLISHED.items():
            for name in published:
                with self.subTest(owner=owner, name=name):
                    self.assertIs(
                        getattr(_facade, name),
                        getattr(_OWNER_MODULES[owner], name),
                    )

    def test_records_are_forwarded(self) -> None:
        owner = _OWNER_MODULES[_RECORD_OWNER]
        for name in _RECORDS:
            with self.subTest(name=name):
                self.assertIs(getattr(_facade, name), getattr(owner, name))

    def test_the_facade_forwards_nothing_else(self) -> None:
        forwarded = {
            name for name in _facade.__dict__
            if not name.startswith("_") and name != _FUTURE_FEATURE
        }
        owned = set(_RECORDS)
        for published in _PUBLISHED.values():
            owned.update(published)
        self.assertEqual(forwarded, owned)


if __name__ == "__main__":
    unittest.main()
