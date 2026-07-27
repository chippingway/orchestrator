# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Workflow stage-handler owners.

Destination for the per-label handler facades that still sit in the flat
``orchestrator.stages`` package. A stage arrives here under its own name and
keeps the lazy hooks it already publishes; the module it vacates stays behind
as a temporary forwarder that reads every name back off the owner instead of
rebuilding one, so both import sites hand back the same object and a
``patch.object`` against either is what the other resolves. A forwarder is
dropped once the callers it serves name the owner directly.

Callers import the owner they need, so this initializer binds nothing: the
dispatcher resolves one handler per issue, and an eager binding here would
charge that import for every other stage's leaves and for the worktree and
GitHub subsystems they reach.
"""
