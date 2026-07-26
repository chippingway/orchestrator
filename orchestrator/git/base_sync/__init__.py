# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Base-synchronization domain owners.

The frozen contexts, requests, snapshots, and decisions one auto-rebase
attempt is threaded through live in ``models``; the pinned-state keys, park
reasons, detour labels, and the shared logger those attempts read and write
live in ``state``; the pinned-state writes, notices, and audit events a
recovered rebase publishes live in ``persistence``, and the terminal answers
a verified recovery comparison produces live in ``outcomes``. The reads that
comparison is built from -- the authenticated branch fetch, the local and
remote head SHAs, and the divergence counts -- live in ``snapshot``, and the
order those reads and answers are asked in lives in ``recovery``. ``refresh``
drives one tick's base fetch, worktree discovery, and per-worktree routing;
``pre_pr`` owns the hardened rebase it runs on a branch nobody has pushed
yet, and ``pr`` owns the order a pushed branch's synchronization asks its
owners in. Those owners are ``eligibility`` for the label, park, PR-state,
recovery, and clean-tree gates a PR-having worktree clears before any rewrite
is attempted, and ``startup`` for the pre-rebase anchor its rebase is begun
from and the abort / route / park its failure takes. What a finished rebase is
force-published with lives in ``publication``, the refusals that keep it from
being published at all live in ``guards``, and the relabel, notice, and audit
event a rebase that really conflicted is handed to its stage with live in
``conflicts``. Callers import the owner they
need directly, so this initializer binds nothing and importing ``state`` or
``pre_pr`` never drags the PyGithub types ``models``, ``refresh``, and
``startup`` annotate their fields with in.
``orchestrator.base_sync`` stays the historical facade for callers that
reach these names through the workflow compatibility surface.
"""
