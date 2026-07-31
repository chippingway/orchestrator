# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, surface, and layering checks for the query owners."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from orchestrator.observability.analytics import query as _package
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
)

_PACKAGE = "orchestrator.observability.analytics.query"

_CONNECTIONS_OWNER = "connections"

_CONNECTION_CACHE_OWNER = "connection_cache"

_EXECUTION_OWNER = "execution"

# The declared inventory. A new owner is a deliberate edit here and a paragraph
# in the module map, which is what the inventory check compares the directory
# against.
_OWNERS = (
    _CONNECTION_CACHE_OWNER,
    _CONNECTIONS_OWNER,
    _EXECUTION_OWNER,
)

# What each owner answers for, declared rather than discovered so a new public
# name is a deliberate edit: a second way to open a socket or run a SELECT is
# a second place the close and the error wrapping could disagree. The dialing
# owner is the error type and the two factories under it, plus the two
# judgments a caller makes about a connection rather than a query; the cache is
# the scope a thread reuses, its teardown, and the entry bookkeeping beneath
# them; execution is the resolved inputs one read carries and the two
# connection paths a SELECT runs through.
_SURFACES = MappingProxyType({
    _CONNECTIONS_OWNER: (
        "AnalyticsReadError",
        "close_quietly",
        "default_connect",
        "default_persistent_connect",
        "is_broken_connection_exc",
    ),
    _CONNECTION_CACHE_OWNER: (
        "analytics_connection",
        "cached_entry",
        "close_thread_local_connection",
        "connection_for_url",
        "discard_broken_connection",
        "open_cached_connection",
    ),
    _EXECUTION_OWNER: (
        "ReadQuery",
        "connect_for_read",
        "execute_select",
        "read_connection",
        "select_rows",
    ),
})

# The flat leaves whose responsibility these owners took over. Any survivor
# would be a second connection cache, or a second answer to what a driver
# failure costs.
_VACATED_LEAVES = (
    "orchestrator/analytics/_connection_cache.py",
    "orchestrator/analytics/connection.py",
    "orchestrator/analytics/query.py",
)

# What an owner here may reach: its siblings and the configuration owner both
# connection paths resolve an omitted `db_url=` through.
_REACHABLE_PREFIXES = (
    _PACKAGE,
    "orchestrator.observability.analytics.config",
    "orchestrator.observability",
    "orchestrator._package",
)

# The package the settings a read resolves against still live on. Both
# connection paths reach them inside the call, through the configuration
# owner, so no owner here may plant it -- binding that import is what would
# make the compatibility package load-bearing rather than retirable.
_ANALYTICS_PACKAGE = "orchestrator.analytics"


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
    """Each owner answers for a narrow, declared surface."""

    def test_public_names_are_the_declared_ones(self) -> None:
        for owner, surface in _SURFACES.items():
            with self.subTest(owner=owner):
                self.assertEqual(_defined_here(owner), surface)

    def test_no_surface_is_declared_twice(self) -> None:
        # The package initializer is a marker, so a name is reached on the
        # owner that defines it rather than published a second time above it.
        self.assertNotIn("__all__", _package.__dict__)
        for owner in _OWNERS:
            with self.subTest(owner=owner):
                self.assertNotIn(
                    "__all__", import_module(_qualified(owner)).__dict__,
                )


class LayeringTest(unittest.TestCase):
    """The owners reach only what they compose, and never the driver."""

    def test_no_owner_reaches_past_what_it_composes(self) -> None:
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            for imported in planted:
                with self.subTest(owner=owner, imported=imported):
                    self.assertTrue(
                        imported.startswith(_REACHABLE_PREFIXES)
                        or imported == "orchestrator",
                        f"{owner} reaches {imported}",
                    )

    def test_no_owner_plants_the_flat_package(self) -> None:
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            with self.subTest(owner=owner):
                self.assertNotIn(_ANALYTICS_PACKAGE, planted)


if __name__ == "__main__":
    unittest.main()
