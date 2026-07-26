# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Worktree naming, creation, recovery, cleanup, and terminal owners.

Slug sanitization, branch and path derivation, and the pinned / legacy
branch resolver live in ``paths``; candidate-branch discovery and the
unpushed-commit probes live in ``recovery``; the issue / PR worktree
creators and the new-commit probe they gate on live in ``creation``; the
decomposer's scratch checkout lifecycle lives in ``decomposition``;
per-issue worktree removal and local branch deletion live in ``cleanup``,
and the question / PR-terminal teardowns that compose them live in
``terminal``. Callers import the owner they need directly, so this
initializer binds nothing and importing one owner never drags the others
in. ``orchestrator.worktree_lifecycle`` stays the historical facade for
callers that reach these helpers through the worktree compatibility
surface.
"""
