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

No facade of this domain's own sits beside the package, and nothing above it
republishes these names either, so each answers on the owner that defines it
and a test intercepting one targets that owner -- ``probes`` for base sync's
divergence check, for the ahead/behind reads the documenting, conflicts, and
validating stages take, and for the first-commit subject behind a fresh dev
PR, ``titles`` for the two helpers that PR falls back to, and ``squash`` for
validating's squash. ``orchestrator.branch_publication`` names only the logger
``rewrite`` reports on -- an operator's filter prefix rather than a module path.
"""
