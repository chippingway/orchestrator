# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, surface, and layering checks for the sync owners."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from orchestrator.observability.analytics import sync as _package
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
    _run_import_probe,
)

_PACKAGE = "orchestrator.observability.analytics.sync"

_COLUMNS_OWNER = "columns"

_RECORDS_OWNER = "records"

_ROWS_OWNER = "rows"

# The declared inventory. A new owner is a deliberate edit here and a paragraph
# in the module map, which is what the inventory check compares the directory
# against.
_OWNERS = (
    _COLUMNS_OWNER,
    _RECORDS_OWNER,
    _ROWS_OWNER,
)

# What each owner answers for, declared rather than discovered so a new public
# name is a deliberate edit: a second way to hash a record or to lay a row out
# is a second place the dedup key or the INSERT's parameter order could
# disagree with the one the table is written through. The parse is the
# encoding a hash is taken over and the five coercions a field is narrowed by;
# the mapping is the statement, the tuple that fills it, the provenance
# travelling beside it, and the two shapes a line resolves to. The inventory
# owner reports nothing because the check reads `__module__`, which only a
# class or a function carries -- its whole surface is the four column names,
# the promoted list, the JSONB pair, and the required keys.
_SURFACES = MappingProxyType({
    _COLUMNS_OWNER: (),
    _RECORDS_OWNER: (
        "canonical_json",
        "content_hash",
        "extra_columns",
        "issue_number",
        "parse_ts",
        "required_columns",
        "required_text",
    ),
    _ROWS_OWNER: (
        "PreparedRecord",
        "RowProvenance",
        "build_insert_sql",
        "prepare_record",
        "row_values",
        "split_row",
    ),
})

# Every caller that has to obtain the row translation from this package: the
# ingest loop that turns each line into a batched tuple, and the run that
# builds the statement those tuples are sent under once.
_CALLERS = (
    "orchestrator.analytics._sync_ingest",
    "orchestrator.analytics._sync_run",
)

# The package the sync's settings and its remaining flat leaves still live on.
# No owner here may plant it -- that is what keeps the compatibility package
# retirable rather than load-bearing, and what makes the forwarding beside it
# one-directional.
_ANALYTICS_PACKAGE = "orchestrator.analytics"

# The driver the ingestion opens its connection with. It is imported lazily
# inside the connect helper, and nothing here dials anything, so a caller that
# only hashes a record or lays a row out must not pay for it -- nor be unable
# to do either on a machine with no Postgres client installed.
_DRIVER_PROBE = """
import sys
import {module}
driver = [name for name in sys.modules if name.split('.')[0] == 'psycopg']
sys.exit(', '.join(driver) if driver else 0)
"""


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
    """The declared owners are the ones on disk."""

    def test_declared_owners_are_the_ones_on_disk(self) -> None:
        directory = Path(_package.__file__).parent
        found = tuple(sorted(
            module_path.stem
            for module_path in directory.glob("*.py")
            if module_path.stem != "__init__"
        ))
        self.assertEqual(found, tuple(sorted(_OWNERS)))


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
    """The owners reach only siblings, never the driver, and every caller
    names the one it composes.
    """

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
        # leaves a historical caller still imports forward *to* these owners,
        # so an import back would close the loop and make the flat package
        # part of what a row translation costs.
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            with self.subTest(owner=owner):
                self.assertNotIn(_ANALYTICS_PACKAGE, planted)

    def test_no_owner_plants_the_driver(self) -> None:
        for owner in _OWNERS:
            probe = _DRIVER_PROBE.format(module=_qualified(owner))
            completed = _run_import_probe(probe)
            with self.subTest(owner=owner):
                self.assertEqual(
                    completed.returncode, 0, msg=completed.stderr,
                )

    def test_every_caller_names_the_mapping_owner(self) -> None:
        for caller in _CALLERS:
            with self.subTest(caller=caller):
                self.assertIn(
                    _qualified(_ROWS_OWNER),
                    _imported_orchestrator_modules(caller),
                )


if __name__ == "__main__":
    unittest.main()
