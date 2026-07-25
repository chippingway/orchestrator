# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Branch-publication domain owners.

Branch inspection -- ahead/behind counts, commit-subject reads, and the
subject-shape predicates they feed -- lives in ``probes``; prefix inference
and PR-title selection live in ``titles``. Callers import the owner they
need directly, so this initializer binds nothing and importing ``probes``
never drags ``titles`` in. ``orchestrator.branch_publication`` stays the
historical facade for callers that still reach these helpers through the
workflow compatibility surface.
"""
