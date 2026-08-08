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
``terminal``. Every worktree name is defined on one of these owners, and
callers import the owner they need directly, so this initializer binds
nothing and importing one owner never drags the others in.

No facade of this domain's own sits beside the package. The aggregate hubs
publish a slice of these names for the callers that read them off one:
``worktrees`` sixteen -- the slug pattern, the two sanitizers, the branch,
root, and worktree-path derivations and the pinned / legacy resolver, the
unpushed-commit probe, the two creators and the new-commit probe, the
decomposer's path, creation, and removal, and the two teardowns -- and
``workflow`` fourteen of those, twelve through ``worktrees`` plus the two
teardowns straight off ``terminal``. Every other name answers on its owner
alone. A hub resolves the owner's own object and caches it, so the sites
share identity but not a later patch: a test intercepting one of these
helpers targets the module its caller reads it off -- ``workflow`` for the
stage handlers, and the owner for the ``git/base_sync/`` and
``workflow/engine/`` callers that import it directly. ``cleanup``,
``creation``, ``decomposition``, and ``terminal`` name their logger
``orchestrator.worktree_lifecycle`` rather than after this package, because
that is the name operator log filters select on.
"""
