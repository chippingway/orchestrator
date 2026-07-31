# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, surface, and layering checks for the analytics owners."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from orchestrator.observability import analytics as _package
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
)

_PACKAGE = "orchestrator.observability.analytics"

_CONFIG_OWNER = "config"

_RETENTION_OWNER = "retention"

_RETENTION_REWRITE_OWNER = "retention_rewrite"

_RETENTION_SCAN_OWNER = "retention_scan"

# The declared inventory. A new owner is a deliberate edit here and a
# paragraph in the module map, which is what the inventory check compares the
# directory against.
_OWNERS = (
    _CONFIG_OWNER,
    _RETENTION_OWNER,
    _RETENTION_REWRITE_OWNER,
    _RETENTION_SCAN_OWNER,
)

# What each owner answers for, declared rather than discovered so a new public
# name is a deliberate edit: these are what a caller reaches for a setting or a
# prune, and an accidental export is a second answer to the same question.
# Configuration is the six knobs, the whole set under the names the analytics
# package publishes them as, the view every adapter reads one back through and
# the two ways it is entered, and the read-path URL fallback. Retention is the
# three entry points one caller each reaches -- the per-tick wrapper and the
# two sinks' by-age prunes -- over a scan that decides what is expired and a
# rewrite that swaps the file out from under it.
_SURFACES = MappingProxyType({
    _CONFIG_OWNER: (
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
    ),
    _RETENTION_OWNER: (
        "prune_old_records",
        "prune_trajectory_records",
        "prune_with_retention_logging",
    ),
    _RETENTION_REWRITE_OWNER: (
        "atomic_rewrite",
        "flush_fd_and_replace",
        "prune_jsonl_records",
        "rewrite_pruned_file",
        "unlink_quietly",
    ),
    _RETENTION_SCAN_OWNER: (
        "PruneScan",
        "normalized_jsonl_line",
        "probe_exists",
        "prune_timestamp",
        "read_kept_records",
    ),
})

# The flat leaves whose responsibility these owners took over. Any survivor
# would be a second place a knob could be parsed from or a sink pruned by.
_VACATED_LEAVES = (
    "orchestrator/analytics/_recording_settings.py",
    "orchestrator/analytics/_retention.py",
    "orchestrator/analytics/_retention_rewrite.py",
    "orchestrator/analytics/_retention_scan.py",
    "orchestrator/analytics/db_url.py",
)

# Every adapter that has to obtain configuration from the owner: the package
# bootstrap that binds the parsed knobs, the append paths of both sinks and the
# prune both are bounded by, the two skill readers that take their holder off
# an exit context, the gate the opt-in trajectory write runs behind, the two
# read-path owners that resolve a query's URL, and the sync request that falls
# back to both sink knobs.
_CONFIG_ADAPTERS = (
    "orchestrator.analytics._package_initialization",
    "orchestrator.observability.analytics.recording.events",
    "orchestrator.observability.analytics.recording.catalog",
    "orchestrator.observability.analytics.recording.skills",
    "orchestrator.observability.analytics.retention",
    "orchestrator.observability.analytics.trajectories.api",
    "orchestrator.observability.analytics.trajectories.persistence",
    "orchestrator.observability.analytics.query.connection_cache",
    "orchestrator.observability.analytics.query.execution",
    "orchestrator.analytics._sync_run",
)

# The compatibility package whose bootstrap rebuilds and republishes the prune.
# The polling tick reaches the same owner, but names it inside the call, so an
# import probe cannot see it -- the once-per-tick cadence is pinned beside
# `main` instead.
_RETENTION_CALLER = "orchestrator.analytics"

# The package the sinks' settings still live on. A prune resolves it inside the
# call, so no owner here may plant it -- that is what keeps the compatibility
# package retirable rather than load-bearing.
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
    """The owners reach nothing outside, and every adapter names them."""

    def test_no_owner_reaches_outside_the_package(self) -> None:
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

    def test_no_owner_plants_the_flat_package(self) -> None:
        # The sharpest case the check above rejects, named on its own: the
        # settings a prune reads live on that package and it is where a caller
        # patches one, so binding an import of it here would cycle -- the
        # package's own bootstrap is what imports these owners.
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            with self.subTest(owner=owner):
                self.assertNotIn(_ANALYTICS_PACKAGE, planted)

    def test_every_adapter_names_the_config_owner(self) -> None:
        # Configuration has one source, so an adapter that parses a knob or
        # re-reads the environment itself would be a second one.
        for adapter in _CONFIG_ADAPTERS:
            with self.subTest(adapter=adapter):
                self.assertIn(
                    _qualified(_CONFIG_OWNER),
                    _imported_orchestrator_modules(adapter),
                )

    def test_the_flat_package_names_the_prune_owner(self) -> None:
        self.assertIn(
            _qualified(_RETENTION_OWNER),
            _imported_orchestrator_modules(_RETENTION_CALLER),
        )


if __name__ == "__main__":
    unittest.main()
