# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Workflow stage-handler owners.

Owner of every per-label stage handler. Each arrived here as its own subpackage
of responsibility-named owners -- ``decomposition``, ``implementing``,
``documenting``, ``validating``, ``in_review``, ``fixing``, ``conflicts``, and
``question`` -- and every one of them has outlived the temporary forwarder it
left behind in the flat ``orchestrator.stages`` package, so a stage's names
answer on the owners here alone. Dispatch names them too: the label table names
the owner a handler lives on, so a patch meant to intercept a dispatched
handler has to land there.

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per issue, and an eager binding here would
charge that import for every other stage's leaves and for the worktree and
GitHub subsystems they reach.
"""
