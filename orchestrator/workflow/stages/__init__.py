# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Workflow stage-handler owners.

Owner of every per-label stage handler. Each stage is a subpackage of
responsibility-named owners -- ``decomposition``, ``implementing``,
``documenting``, ``validating``, ``in_review``, ``fixing``, ``conflicts``,
``question``, and ``discussion`` -- and these are the only modules a stage's
names answer on, so a ``patch.object`` on the owner is the only interception a
caller can need.
Dispatch names them too: the label table names the owner a handler lives on, so
a patch meant to intercept a dispatched handler has to land there.

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per issue, and an eager binding here would
charge that import for every other stage's leaves and for the worktree and
GitHub subsystems they reach.
"""
