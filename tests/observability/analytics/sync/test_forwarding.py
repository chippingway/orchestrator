# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat analytics modules still answer for on the sync side."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType

_SYNC_FACADE = "orchestrator.analytics.sync"

_COLUMNS = "orchestrator.observability.analytics.sync.columns"

_RECORDS = "orchestrator.observability.analytics.sync.records"

_ROWS = "orchestrator.observability.analytics.sync.rows"

# The historical private spelling each flat leaf publishes, and the owner
# attribute it resolves to. A private name a caller reached through one of
# these modules is still a name it reached, so it has to keep answering -- with
# the owner's object, not a copy the leaf kept.
_COLUMN_NAMES = (
    ("_COL_EVENT", _COLUMNS, "COL_EVENT"),
    ("_COL_ISSUE", _COLUMNS, "COL_ISSUE"),
    ("_COL_REPO", _COLUMNS, "COL_REPO"),
    ("_COL_TS", _COLUMNS, "COL_TS"),
    ("_JSONB_COLUMNS", _COLUMNS, "JSONB_COLUMNS"),
    ("_PROMOTED_COLUMNS", _COLUMNS, "PROMOTED_COLUMNS"),
    ("_REQUIRED_KEYS", _COLUMNS, "REQUIRED_KEYS"),
)

_RECORD_NAMES = (
    ("_canonical_json", _RECORDS, "canonical_json"),
    ("_content_hash", _RECORDS, "content_hash"),
    ("_extra_columns", _RECORDS, "extra_columns"),
    ("_issue_number", _RECORDS, "issue_number"),
    ("_parse_ts", _RECORDS, "parse_ts"),
    ("_required_columns", _RECORDS, "required_columns"),
    ("_required_text", _RECORDS, "required_text"),
)

_ROW_NAMES = (
    ("_PreparedRecord", _ROWS, "PreparedRecord"),
    ("_RowProvenance", _ROWS, "RowProvenance"),
    ("_build_insert_sql", _ROWS, "build_insert_sql"),
    ("_prepare_record", _ROWS, "prepare_record"),
    ("_row_values", _ROWS, "row_values"),
    ("_split_row", _ROWS, "split_row"),
)

# The flat modules a caller reaches the translation through, and what each name
# they publish resolves to. The hub is the union of the three leaves beneath
# it, because it is the spelling the ingest and the facade were written
# against: a caller naming either has to land on the one column list the INSERT
# is built from and the one hash the dedup arbitrates on.
_FORWARDED_MODULES = MappingProxyType({
    "orchestrator.analytics._sync_row_schema": _COLUMN_NAMES,
    "orchestrator.analytics._sync_row_parse": _RECORD_NAMES,
    "orchestrator.analytics._sync_row_mapping": _ROW_NAMES,
    "orchestrator.analytics._sync_rows": (
        *_COLUMN_NAMES,
        *_RECORD_NAMES,
        *_ROW_NAMES,
    ),
})

# What the sync facade binds at import out of the four mapping objects the CLI
# drives. It resolves them through the hub above, so this pins the far end of
# that chain: the statement, the tuple, the provenance beside it, and the parse
# a line enters through are the owner's own.
_FORWARDED_FACADE = (
    ("_RowProvenance", _ROWS, "RowProvenance"),
    ("_build_insert_sql", _ROWS, "build_insert_sql"),
    ("_prepare_record", _ROWS, "prepare_record"),
    ("_row_values", _ROWS, "row_values"),
)


class ForwardedFlatModuleTest(unittest.TestCase):
    """Every name the flat sync modules publish is the owner's own object."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        for module_name, forwarded in _FORWARDED_MODULES.items():
            for name, owner_name, attribute in forwarded:
                with self.subTest(module=module_name, name=name):
                    self.assertIs(
                        getattr(import_module(module_name), name),
                        getattr(import_module(owner_name), attribute),
                    )

    def test_no_flat_module_defines_one_itself(self) -> None:
        # What keeps the forwarding thin: a module that defined a name of its
        # own would be a second implementation the check above cannot see,
        # because it only compares the names the module was asked for.
        for module_name in _FORWARDED_MODULES:
            defined = tuple(
                name
                for name, member in import_module(module_name).__dict__.items()
                if getattr(member, "__module__", None) == module_name
            )
            with self.subTest(module=module_name):
                self.assertEqual(defined, ())


class ForwardedSyncFacadeTest(unittest.TestCase):
    """The CLI surface binds the mapping owner's objects, not copies."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        facade = import_module(_SYNC_FACADE)
        for name, owner_name, attribute in _FORWARDED_FACADE:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(facade, name),
                    getattr(import_module(owner_name), attribute),
                )


if __name__ == "__main__":
    unittest.main()
