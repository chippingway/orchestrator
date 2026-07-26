# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Base-synchronization domain owners.

The frozen contexts, requests, snapshots, and decisions one auto-rebase
attempt is threaded through live in ``models``; the pinned-state keys, park
reasons, detour labels, and the shared logger those attempts read and write
live in ``state``; the pinned-state writes, notices, and audit events a
recovered rebase publishes live in ``persistence``, and the terminal answers
a verified recovery comparison produces live in ``outcomes``. Callers import
the owner they need directly, so this initializer binds nothing and importing
``state`` never drags the PyGithub types ``models`` annotates its fields with
in. ``orchestrator.base_sync`` stays the historical facade for callers that
reach these names through the workflow compatibility surface.
"""
