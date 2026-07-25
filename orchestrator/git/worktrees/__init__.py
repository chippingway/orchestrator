# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Worktree naming and recovery owners.

Slug sanitization, branch and path derivation, and the pinned / legacy
branch resolver live in ``paths``; candidate-branch discovery and the
unpushed-commit probes live in ``recovery``. Callers import the owner they
need directly, so this initializer binds nothing and importing one owner
never drags the other in. ``orchestrator.worktree_lifecycle`` stays the
historical facade for callers that reach these helpers through the worktree
compatibility surface.
"""
