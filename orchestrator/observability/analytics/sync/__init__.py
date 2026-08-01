# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics synchronization owners.

Destination for the ingestion that fills the operator's Postgres target from
the project-local JSONL: the command it is driven by, the row parsing and
mapping between the two shapes, the deduplicating insert, and the database
lifecycle around it.

The translation between the two shapes is here already, split by what each
half is answerable to. ``columns`` owns the inventory the record shape and the
table shape meet on -- what a record must carry, what has a column of its own,
and which of those columns hold JSON. ``records`` owns what one record hashes
to, pinned to the encoding the sink wrote its line with because that hash is
the key the insert deduplicates on, plus the coercion each required field is
either narrowed by or refused for. ``rows`` owns the line itself: the
statement a batch is sent under, the positional tuple built from the same
column list in the same order so no per-row mapping stands between them, and
the reason a line that cannot become a row is skipped for rather than raised
on. None of the three names a driver, so a caller can build or hash a row
without Postgres installed.

Callers import the owner they need, so this initializer binds nothing: the
sync is its own command run against its own schema, and nothing in the
polling loop should pay for its imports.
"""
