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

No facade of this domain's own sits beside the package. The aggregate hubs
publish a slice of these names for the callers that read them off one:
``worktrees`` nine -- the divergence and subject probes, the
conventional-commit pattern behind them, the two title helpers, and the
squash entry point -- ``workflow`` seven of those through it, all but the
pattern and the recent-base-subject read, and ``base_sync`` the divergence
probe its own owners call. Every other name answers on its owner alone. A
hub resolves the owner's own object and caches it, so the sites share
identity but not a later patch: a test intercepting one of these helpers
targets the module its caller reads it off -- ``workflow`` for the stage
helpers, and the owner for base sync's divergence check and validating's
squash. ``orchestrator.branch_publication`` names only the logger ``rewrite``
reports on -- an operator's filter prefix rather than a module path.
"""
