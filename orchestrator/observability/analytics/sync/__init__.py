# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Analytics synchronization owners.

Destination for the ingestion that fills the operator's Postgres target from
the project-local JSONL: the command it is driven by, the row parsing and
mapping between the two shapes, the deduplicating insert, and the database
lifecycle around it.

Callers import the owner they need, so this initializer binds nothing: the
sync is its own command run against its own schema, and nothing in the
polling loop should pay for its imports.
"""
