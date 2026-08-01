# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat analytics modules still answer for on the sync side."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType

_SYNC_FACADE = "orchestrator.analytics.sync"

_PACKAGE = "orchestrator.observability.analytics.sync"

_COLUMNS = f"{_PACKAGE}.columns"

_DATABASE = f"{_PACKAGE}.database"

_INGEST = f"{_PACKAGE}.ingest"

_MODELS = f"{_PACKAGE}.models"

_RECORDS = f"{_PACKAGE}.records"

_REDACTION = f"{_PACKAGE}.redaction"

_ROWS = f"{_PACKAGE}.rows"

_RUN = f"{_PACKAGE}.run"

_ENTRY_POINT = "sync_jsonl_to_postgres"

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

# The result keeps its public spelling; the two the loop threads keep the
# private ones they were published under.
_MODEL_NAMES = (
    ("SyncResult", _MODELS, "SyncResult"),
    ("_SyncCounters", _MODELS, "SyncCounters"),
    ("_IngestContext", _MODELS, "IngestContext"),
)

_REDACTION_NAMES = (
    ("_redact_db_url", _REDACTION, "redact_db_url"),
    ("_redacted_netloc", _REDACTION, "redacted_netloc"),
    ("_redacted_query", _REDACTION, "redacted_query"),
)

# The view name travels with the two cleanups and the refresh that reads it, so
# a caller cannot reach a rebuild through one module and the view it rebuilds
# through another.
_DATABASE_NAMES = (
    ("_DAILY_ROLLUP_VIEW", _DATABASE, "DAILY_ROLLUP_VIEW"),
    ("_close_quietly", _DATABASE, "close_quietly"),
    ("_default_connect", _DATABASE, "default_connect"),
    ("_default_json_adapter", _DATABASE, "default_json_adapter"),
    ("_execute_rollup_refresh", _DATABASE, "execute_rollup_refresh"),
    ("_refresh_daily_rollup", _DATABASE, "refresh_daily_rollup"),
    ("_rollback_quietly", _DATABASE, "rollback_quietly"),
)

# The buffer size is one of these names: the loop reads it off its owner when a
# pass starts, so what is bound out here reports the size rather than setting
# it.
_INGEST_NAMES = (
    ("_BATCH_SIZE", _INGEST, "BATCH_SIZE"),
    ("_RecordIngester", _INGEST, "RecordIngester"),
    ("_emit_progress", _INGEST, "emit_progress"),
    ("_existing_hashes", _INGEST, "existing_hashes"),
    ("_flush_batch", _INGEST, "flush_batch"),
    ("_ingest_records", _INGEST, "ingest_records"),
    ("_note_malformed_line", _INGEST, "note_malformed_line"),
    ("_stream_records", _INGEST, "stream_records"),
)

_RUN_NAMES = (
    ("_SyncRequest", _RUN, "SyncRequest"),
    ("_SyncRun", _RUN, "SyncRun"),
)

# The flat modules a caller reaches the sync through, and what each name they
# publish resolves to. The row hub is the union of the three leaves beneath it,
# because it is the spelling the ingest and the facade were written against: a
# caller naming either has to land on the one column list the INSERT is built
# from and the one hash the dedup arbitrates on.
_FORWARDED_MODULES = MappingProxyType({
    "orchestrator.analytics._sync_row_schema": _COLUMN_NAMES,
    "orchestrator.analytics._sync_row_parse": _RECORD_NAMES,
    "orchestrator.analytics._sync_row_mapping": _ROW_NAMES,
    "orchestrator.analytics._sync_rows": (
        *_COLUMN_NAMES,
        *_RECORD_NAMES,
        *_ROW_NAMES,
    ),
    "orchestrator.analytics._sync_models": _MODEL_NAMES,
    "orchestrator.analytics._sync_redaction": _REDACTION_NAMES,
    "orchestrator.analytics._sync_database": _DATABASE_NAMES,
    "orchestrator.analytics._sync_ingest": _INGEST_NAMES,
    "orchestrator.analytics._sync_run": _RUN_NAMES,
})

# What the sync facade binds at import out of the owners the CLI drives. It
# resolves most of them through the leaves above, so this pins the far end of
# that chain: whichever module a historical caller named, the object it holds
# is the one the replay runs on.
_FORWARDED_FACADE = (
    ("_RowProvenance", _ROWS, "RowProvenance"),
    ("_build_insert_sql", _ROWS, "build_insert_sql"),
    ("_prepare_record", _ROWS, "prepare_record"),
    ("_row_values", _ROWS, "row_values"),
    *_MODEL_NAMES,
    *_REDACTION_NAMES,
    *_DATABASE_NAMES,
    *_INGEST_NAMES,
    *_RUN_NAMES,
    (_ENTRY_POINT, _RUN, _ENTRY_POINT),
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
    """The CLI surface binds the owners' objects, not copies."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        facade = import_module(_SYNC_FACADE)
        for name, owner_name, attribute in _FORWARDED_FACADE:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(facade, name),
                    getattr(import_module(owner_name), attribute),
                )

    def test_the_entry_point_is_the_one_the_cli_calls(self) -> None:
        # The command reads the name off its own module at call time, which is
        # what lets an operator-facing failure be simulated by patching there;
        # binding it into `_run_cli` instead would leave that interception
        # pointing at nothing.
        facade = import_module(_SYNC_FACADE)
        self.assertIs(
            facade._run_cli.__globals__[_ENTRY_POINT],
            getattr(import_module(_RUN), _ENTRY_POINT),
        )


if __name__ == "__main__":
    unittest.main()
