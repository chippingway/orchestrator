# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Workflow stage-handler owners.

Owner of every per-label stage handler. Each arrived here as its own subpackage
of responsibility-named owners -- ``decomposition``, ``implementing``,
``documenting``, ``validating``, ``in_review``, ``fixing``, ``conflicts``, and
``question`` -- and
the module a stage vacated in the flat ``orchestrator.stages`` package stays
behind as a temporary forwarder that reads every name
back off those owners instead of rebuilding one, so both import sites hand back
the same object. Identity is all a forwarder carries: it caches what it resolved,
so a ``patch.object`` intercepts the lookup site it lands on rather than both,
and the owner is the site orchestrator code reads. Dispatch makes that explicit
-- the label table names the owner a handler lives on, so a patch meant
to intercept a dispatched handler has to land there. A forwarder is dropped once
the callers it serves name the owner directly, which ``validating``,
``in_review``, ``question``, ``decomposition``, ``implementing``, and
``conflicts`` have already outlived: their names answer on the owners here
alone.

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per issue, and an eager binding here would
charge that import for every other stage's leaves and for the worktree and
GitHub subsystems they reach.
"""
