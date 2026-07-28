# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory viewer owners.

Destination for the second Streamlit page -- the file-backed viewer that
reads the trajectory JSONL directly, usage and cost included, and needs no
Postgres: the pure filter and summary read model, the run views built from
it, and the HTML a page is rendered from.

Callers import the owner they need, so this initializer binds nothing, and
Streamlit stays behind a function-local import for the same reason it does
in ``dashboard`` -- with one more: the read model here is pure, and its
value is that it stays importable, and testable, in an install carrying no
viewer dependencies at all.
"""
