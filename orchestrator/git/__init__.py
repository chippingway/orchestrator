# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Git execution domain owners.

Plain and hardened `git` invocation together with the local
transport-config probe live in ``commands``; the token-bearing askpass
session, the authenticated fetches, and the hardened push live in
``authentication``; the process-local per-target-root lock registry lives
in ``locks``. Every git-execution name is defined on one of these owners,
and callers import the owner they need directly, so this initializer binds
nothing and an import pulls in only what the chosen owner itself needs --
``authentication`` builds on ``commands`` and ``locks``, while those two
depend on nothing else in the package.

No facade of this domain's own sits beside the package. The aggregate hubs
publish a slice of these names for the callers that read them off one:
``worktrees`` nine -- the two authenticated fetches and the push, the
no-prompt environment and the plain and hardened runners, and the lock
registry, its guard, and the per-root lock -- and ``workflow`` five of
those through ``worktrees``, the fetches and the push plus the two
runners. Every other name answers on its owner alone. A
hub resolves the owner's own object and caches it, so the sites share
identity but not a later patch: a test intercepting one of these helpers
targets the module its caller reads it off -- ``workflow`` for the stage
git calls, and the owner for the ``git/worktrees/`` and ``git/publication/``
callers that import it directly. ``authentication`` names its logger
``orchestrator.git_plumbing`` rather than after this package, because that
is the name operator log filters select on.
"""
