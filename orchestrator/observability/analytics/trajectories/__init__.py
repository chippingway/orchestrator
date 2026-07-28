# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory sink owners.

Destination for the opt-in, default-off per-run reasoning sink: the record
models, the redaction and head/tail truncation a step timeline is sanitized
by, and the append and pruning that persist what survives.

Callers import the owner they need, so this initializer binds nothing. The
sink is filled from inside a tracked agent run, so it stays free of the
query and viewer graphs that later read it back.
"""
