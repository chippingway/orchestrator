# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, layering, and forwarding checks for the skill owners."""
from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch

from orchestrator import (
    _workflow_export_manifest,
    skill_catalog as _facade,
    skills as _package,
    workflow as _workflow,
)


_PACKAGE = "orchestrator.skills"

_FACADE = "orchestrator.skill_catalog"

_CATALOG_OWNER = "catalog"

_DISCOVERY_OWNER = "discovery"

# The declared inventory. A new owner is a deliberate edit here and a paragraph
# in the module map, which is what the inventory check compares the directory
# against.
_OWNERS = (_CATALOG_OWNER, _DISCOVERY_OWNER)

# Bound at module scope, so collecting this file is what plants both owners in
# `sys.modules` rather than whichever scenario test happened to run first.
_OWNER_MODULES = MappingProxyType({
    owner: import_module(f"{_PACKAGE}.{owner}") for owner in _OWNERS
})

# What the compatibility site forwards, grouped by the owner defining it: the
# per-tick producer the workflow facade still exports, and the two per-run codex
# collectors with the baseline one of them answers with.
_FORWARDED = MappingProxyType({
    _CATALOG_OWNER: ("_emit_repo_skill_catalog",),
    _DISCOVERY_OWNER: (
        "_CODEX_OFFERED_TOOLS",
        "discover_codex_tools",
        "discover_local_skills",
    ),
})

_EMIT_CATALOG = "_emit_repo_skill_catalog"

# The one pass that drives the catalog owner, and the only workflow module that
# names it.
_TICK = "orchestrator.workflow.engine.tick"

# A catalog is observation the tick drives, never state a handler consults, so
# no owner may read the workflow engine, a stage, or an application entrypoint
# back. The flat `_workflow_*` inventory is the sharpest entry: resolving any
# name on it imports the leaf that holds it.
_FORBIDDEN_PREFIXES = (
    "orchestrator.__main__",
    "orchestrator._main",
    "orchestrator._workflow",
    "orchestrator.cli",
    "orchestrator.main",
    "orchestrator.stages",
    "orchestrator.workflow",
)

# What `import orchestrator` alone plants, so the cost checks can hold a module
# to its own chain and nothing besides.
_ROOT_PACKAGE_MODULES = frozenset((
    "orchestrator",
    "orchestrator._package_exports",
))

_RESOLVER_HOOKS = ("__dir__", "__getattr__")

# The compatibility site's own inventory tuple and the feature flag
# `from __future__ import annotations` binds are not names it forwards.
_UNFORWARDED_BINDINGS = frozenset(("_COMPATIBILITY_EXPORTS", "annotations"))

_PROBE_PATH = Path("/tmp/orchestrator-skills-owner-probe")

# A codex exit context with a worktree and both skill sinks on, which is what
# makes the writer reach for discovery at all.
_CODEX_CONTEXT = SimpleNamespace(
    cwd=_PROBE_PATH,
    analytics_package=SimpleNamespace(
        TRACK_SKILL_TRIGGERS=True,
        TRAJECTORY_LOG_PATH=_PROBE_PATH,
    ),
)

_IMPORTED_MODULES_SCRIPT = """
import sys
import {module}
print(*sorted(name for name in sys.modules if name.startswith('orchestrator')))
"""


def _imported_orchestrator_modules(module: str) -> frozenset[str]:
    """Names of the orchestrator modules a fresh `import module` plants."""
    completed = subprocess.run(
        [sys.executable, "-c", _IMPORTED_MODULES_SCRIPT.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
    )
    return frozenset(completed.stdout.split())


class CleanProcessImportTest(unittest.TestCase):
    """The package, each owner, and the site left behind all import alone.

    A subprocess per module gives each one a `sys.modules` no earlier import
    has populated, which is the only place a cycle shows up at all: the
    analytics package `catalog` writes through reaches back into this one for
    a codex run's offered skills, and a suite that has already imported half
    the tree resolves the other half off what the first half left behind.
    """

    def test_each_module_imports_standalone(self) -> None:
        owners = (module.__name__ for module in _OWNER_MODULES.values())
        for module_name in (_PACKAGE, _FACADE, *owners):
            with self.subTest(module=module_name):
                completed = subprocess.run(
                    [sys.executable, "-c", f"import {module_name}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)


class LayeringTest(unittest.TestCase):
    """The package points away from the workflow and costs nothing eagerly."""

    def test_package_import_costs_only_its_own_chain(self) -> None:
        # A marker initializer binds nothing, so the analytics writer reaching
        # for `discovery` is not charged for the sink and the git execution
        # `catalog` is built on.
        self.assertEqual(
            _imported_orchestrator_modules(_PACKAGE),
            _ROOT_PACKAGE_MODULES | {_PACKAGE},
        )

    def test_no_owner_reaches_the_workflow_layer(self) -> None:
        for owner, module in _OWNER_MODULES.items():
            planted = _imported_orchestrator_modules(module.__name__)
            for imported in planted:
                with self.subTest(owner=owner, imported=imported):
                    self.assertFalse(
                        imported.startswith(_FORBIDDEN_PREFIXES),
                        f"{owner} inverts the dependency via {imported}",
                    )

    def test_no_owner_reaches_the_compatibility_site(self) -> None:
        # An owner reading the temporary module back would both cycle and make
        # it load-bearing rather than deletable.
        for owner, module in _OWNER_MODULES.items():
            with self.subTest(owner=owner):
                self.assertNotIn(
                    _FACADE, _imported_orchestrator_modules(module.__name__),
                )

    def test_discovery_reaches_no_sibling(self) -> None:
        # The roots and the `SKILL.md` marker are defined on `discovery` rather
        # than `catalog` precisely so the direction can run this way: a codex
        # run's filesystem scan pays for nothing but the standard library.
        owner = _OWNER_MODULES[_DISCOVERY_OWNER].__name__
        self.assertEqual(
            _imported_orchestrator_modules(owner),
            _ROOT_PACKAGE_MODULES | {_PACKAGE, owner},
        )


class PackageSurfaceTest(unittest.TestCase):
    """The initializer is a marker over exactly the owners on disk."""

    def test_declared_owners_are_the_ones_on_disk(self) -> None:
        directory = Path(_package.__file__).parent
        found = tuple(sorted(
            module_path.stem
            for module_path in directory.glob("*.py")
            if module_path.stem != "__init__"
        ))
        self.assertEqual(found, tuple(sorted(_OWNERS)))

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

    def test_no_surface_or_resolver_declared(self) -> None:
        # Callers name an owner, so there is nothing here to publish and no
        # lazy inventory to rebuild -- a hook or an `__all__` would be the
        # facade this destination replaces.
        self.assertNotIn("__all__", _package.__dict__)
        for hook in _RESOLVER_HOOKS:
            with self.subTest(hook=hook):
                self.assertNotIn(hook, _package.__dict__)

    def test_no_flat_leaf_is_left_behind(self) -> None:
        # The migration is only finished when every scan resolves off an owner
        # here; a `_local_skills` leaf beside the compatibility site would be
        # one the flat package still owns.
        package_root = Path(import_module("orchestrator").__file__).parent
        self.assertEqual(list(package_root.glob("_local_skills*.py")), [])


class ForwardedSurfaceTest(unittest.TestCase):
    """The compatibility site hands back the owners' own objects."""

    def test_the_site_forwards_the_owner_objects(self) -> None:
        for owner, forwarded in _FORWARDED.items():
            module = _OWNER_MODULES[owner]
            for name in forwarded:
                with self.subTest(owner=owner, name=name):
                    self.assertIs(getattr(_facade, name), getattr(module, name))

    def test_the_site_forwards_nothing_else(self) -> None:
        forwarded = {
            name for name in _facade.__dict__
            if not name.startswith("__")
            and name not in _UNFORWARDED_BINDINGS
        }
        owned = set()
        for names in _FORWARDED.values():
            owned.update(names)
        self.assertEqual(forwarded, owned)


class CallSiteTest(unittest.TestCase):
    """Neither live producer resolves through the site left behind."""

    def test_the_tick_names_the_catalog_owner(self) -> None:
        # The per-tick pass is reached on its owner rather than as a facade
        # attribute, so that is where a test intercepting it has to patch --
        # and the tick pays for the owner at import, never the site.
        planted = _imported_orchestrator_modules(_TICK)
        self.assertIn(_OWNER_MODULES[_CATALOG_OWNER].__name__, planted)
        self.assertNotIn(_FACADE, planted)

    def test_the_facade_still_forwards_the_owner(self) -> None:
        # The historical export outlives the call site that used to resolve
        # through it, and it answers with the owner's own object.
        owner = _OWNER_MODULES[_CATALOG_OWNER]
        targets = [
            target.module_name
            for target in _workflow_export_manifest.EXPORTS
            if target.export_name == _EMIT_CATALOG
        ]
        self.assertEqual(targets, [owner.__name__])
        self.assertIs(
            getattr(_workflow, _EMIT_CATALOG), getattr(owner, _EMIT_CATALOG),
        )

    def test_no_manifest_target_names_the_site(self) -> None:
        for target in _workflow_export_manifest.EXPORTS:
            with self.subTest(name=target.export_name):
                self.assertNotEqual(target.module_name, _FACADE)

    def test_codex_backfill_reads_the_owner(self) -> None:
        # Patching the owner is what intercepts a codex run's offered skills
        # and tools, which holds only while the writer names it: the site left
        # behind binds the same objects but resolves nothing later.
        from orchestrator.observability.analytics.recording import (
            catalog as recording_catalog,
            models as recording_models,
        )

        owner = _OWNER_MODULES[_DISCOVERY_OWNER]
        catalog = recording_models.CodexCatalog()
        with patch.object(
            owner, "discover_local_skills", lambda _cwd: ("scanned",),
        ), patch.object(
            owner, "discover_codex_tools", lambda: ("offered",),
        ):
            recording_catalog.populate_codex_catalog(_CODEX_CONTEXT, catalog)
        self.assertEqual(catalog.available_skills, ["scanned"])
        self.assertEqual(catalog.tools, ["offered"])


if __name__ == "__main__":
    unittest.main()
