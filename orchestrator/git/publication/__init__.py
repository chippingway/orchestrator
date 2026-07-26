# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Branch-publication domain owners.

Branch inspection -- ahead/behind counts, commit-subject reads, and the
subject-shape predicates they feed -- lives in ``probes``; prefix inference
and PR-title selection live in ``titles``; the preconditions a squash is
planned from live in ``planning``; the reset, commit, force-push, and
rollback that spend that plan live in ``rewrite``; and ``squash`` composes
the two halves into the entry point stage handlers call. Callers import the
owner they need directly, so this initializer binds nothing and importing
``probes`` never drags the rewrite path in.
``orchestrator.branch_publication`` stays the historical facade for callers
that still reach these helpers through the workflow compatibility surface.
"""
