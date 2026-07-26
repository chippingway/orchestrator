# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The single route from an interrupted auto-rebase to one terminal answer.

The verified facts arrive from ``snapshot`` and the answers live in
``outcomes``; what this owner adds is the order they are asked in, and that
order is the safety property. An ineligible label is cleared before anything
is fetched, an unmoved HEAD falls back to the normal rebase flow before any
comparison is trusted, and equality with the remote is checked before the
ahead/behind counts are -- so the reissued force-push is only ever reached by
a head proven to be ahead of a remote the tick actually read. Anything else
parks. The legacy keyword signature is bound here too, because the flat
callers still pass the pre-context argument list this route derives its
context from.
"""
from __future__ import annotations

import inspect
from typing import Any

from orchestrator.git import authentication
from orchestrator.git.base_sync import outcomes, persistence, snapshot
from orchestrator.git.base_sync.models import (
    _AutoRebaseRecoveryContext,
    _AutoRebaseRecoverySnapshot,
)
from orchestrator.git.base_sync.state import _PR_REFRESH_DETOUR_LABELS
from orchestrator.git.verification import probes as verification_probes

_RECOVERY_SIGNATURE = inspect.Signature((
    inspect.Parameter("gh", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("spec", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("issue", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("state", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("worktree", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("pr_number", inspect.Parameter.KEYWORD_ONLY),
    inspect.Parameter("label", inspect.Parameter.KEYWORD_ONLY),
    inspect.Parameter(
        "pending_pre_rebase_sha",
        inspect.Parameter.KEYWORD_ONLY,
    ),
    inspect.Parameter("behind", inspect.Parameter.KEYWORD_ONLY, default=0),
    inspect.Parameter(
        "unparking_consumed_max",
        inspect.Parameter.KEYWORD_ONLY,
        default=None,
    ),
))


def _retry_recovery_push(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Publish a verified ahead-only recovery head and finalize its state."""
    dirty_files = verification_probes._worktree_dirty_files(context.worktree)
    if dirty_files:
        return outcomes._park_dirty_recovery(
            context, recovery_snapshot, dirty_files,
        )
    if not authentication._push_branch(
        context.spec,
        context.worktree,
        recovery_snapshot.branch,
        force_with_lease=context.pending_pre_rebase_sha,
    ):
        return outcomes._park_failed_recovery_push(context, recovery_snapshot)
    return persistence._finalize_recovered_rebase(
        context,
        local_head=recovery_snapshot.local_head,
        method="crash_recovery_pushed",
        notice=outcomes._pushed_recovery_notice(
            context, recovery_snapshot.local_head,
        ),
    )


def _recover_pending_auto_base_rebase_context(
    context: _AutoRebaseRecoveryContext,
) -> bool:
    """Route an interrupted auto-rebase from verified local/remote state."""
    if context.label not in _PR_REFRESH_DETOUR_LABELS:
        return snapshot._clear_ineligible_recovery(context)

    recovery_snapshot = snapshot._fetch_recovery_snapshot(context)
    if recovery_snapshot is None:
        return True
    if (
        recovery_snapshot.local_head
        and recovery_snapshot.local_head == context.pending_pre_rebase_sha
    ):
        return snapshot._clear_unchanged_recovery(context)

    return _route_recovery_snapshot(context, recovery_snapshot)


def _route_recovery_snapshot(
    context: _AutoRebaseRecoveryContext,
    recovery_snapshot: _AutoRebaseRecoverySnapshot,
) -> bool:
    """Route a changed-head recovery from its completed local/remote compare."""
    completed = snapshot._complete_recovery_snapshot(
        context, recovery_snapshot,
    )
    if completed is None:
        return True
    if completed.local_head and completed.local_head == completed.remote_head:
        return outcomes._finalize_already_published_recovery(
            context, completed,
        )
    if completed.ahead == 0 and completed.behind == 0:
        return outcomes._reject_unknown_recovery_comparison(context, completed)
    if completed.behind > 0:
        return outcomes._park_diverged_recovery(context, completed)
    return _retry_recovery_push(context, completed)


def _recover_pending_auto_base_rebase(
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Finalize a clean auto-base-rebase interrupted by a prior crash.

    The pinned pre-rebase SHA distinguishes an unchanged worktree, an
    already-published rewrite, an ahead-only rewrite that still needs a
    push, and a branch that diverged through an out-of-band update. Returns
    False only when HEAD still equals the anchor and the normal rebase flow
    should continue on the same tick.
    """
    bound_fields = _RECOVERY_SIGNATURE.bind(*args, **kwargs)
    bound_fields.apply_defaults()
    context = _AutoRebaseRecoveryContext(**bound_fields.arguments)
    return _recover_pending_auto_base_rebase_context(context)


_recover_pending_auto_base_rebase.__signature__ = _RECOVERY_SIGNATURE
