# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Force-publishing one clean rebase, and the surfaces it then lands on.

The lease-pinned push is the commit point of the whole auto-rebase: until
the rewritten branch is on the remote, the head the reviewer votes on is
still the pre-rebase SHA. So every check that can still refuse -- an
unreadable HEAD, a rewrite that moved nothing, a tree that came back dirty
-- runs before it and hands off to ``guards``, and the lease itself is
pinned to that same pre-rebase SHA so a foreign update rejects the push
instead of being clobbered. Only an accepted push earns the tail: the PR
notice, the audit event, the `validating` relabel, and last the
`write_pinned_state` that commits the cleared anchor and reset review
round, so a tick that dies partway leaves the anchor pinned for the next
one to recover from.
"""
from __future__ import annotations

from orchestrator.git import authentication
from orchestrator.git.base_sync import guards
from orchestrator.git.base_sync.models import _AutoRebaseContext
from orchestrator.git.base_sync.state import (
    _PENDING_PUSH_SHA,
    _REVIEW_ROUND,
    log,
)
from orchestrator.git.verification import probes
from orchestrator.git.worktrees import paths
from orchestrator.workflow.state import WorkflowLabel, stage_name


def _post_auto_rebase_notice(
    context: _AutoRebaseContext,
    after_sha: str,
) -> None:
    """Post the best-effort PR notice for a published clean rebase."""
    # Lazy import: the comment owner sits in the workflow layer above this
    # package, so binding it at module load would make every git-side
    # import pay for the GitHub client and prompt state it pulls in.
    from orchestrator.workflow.engine import comments as _comments
    spec = context.spec
    after_short = after_sha[:8]
    try:
        _comments._post_pr_comment(
            context.gh,
            context.pr_number,
            context.state,
            f":mag: PR was {context.behind} commit(s) behind "
            f"`{spec.remote_name}/{spec.base_branch}`; "
            "orchestrator auto-rebased the branch and re-pushed it. "
            f"Routing `{context.label}` -> `{WorkflowLabel.VALIDATING}` so "
            f"the reviewer re-runs against the new head (`{after_short}`).",
        )
    except Exception:
        log.exception(
            "issue=#%s could not post auto-rebase notice to PR #%s",
            context.issue.number,
            context.pr_number,
        )


def _emit_auto_rebase_event(
    context: _AutoRebaseContext,
    after_sha: str,
) -> None:
    """Emit the stable audit shape for a published clean rebase."""
    context.gh.emit_event(
        "base_rebased",
        issue_number=context.issue.number,
        stage=stage_name(context.label),
        pr_number=context.pr_number,
        sha=after_sha,
        method="auto_clean_rebase",
        review_round=int(context.state.get(_REVIEW_ROUND) or 0),
        retry_count=context.state.get("retry_count"),
    )


def _finalize_auto_rebase(
    context: _AutoRebaseContext,
    branch: str,
    after_sha: str,
) -> None:
    """Publish the notice, audit event, validating route, and pinned state."""
    _post_auto_rebase_notice(context, after_sha)
    context.state.set(_PENDING_PUSH_SHA, None)
    context.state.set(_REVIEW_ROUND, 0)
    log.info(
        "issue=#%d auto base rebase pushed %s/%s -> %s; routing %r -> "
        "validating",
        context.issue.number,
        context.spec.remote_name,
        branch,
        after_sha[:8],
        context.label,
    )
    _emit_auto_rebase_event(context, after_sha)
    context.gh.set_workflow_label(context.issue, WorkflowLabel.VALIDATING)
    context.gh.write_pinned_state(context.issue, context.state)


def _publish_auto_rebase(
    context: _AutoRebaseContext,
    before_sha: str,
) -> None:
    """Validate and force-publish a successfully rebased PR worktree."""
    after_sha = probes._head_sha(context.worktree)
    if not after_sha:
        guards._park_unreadable_post_rebase_head(context, before_sha)
        return
    if after_sha == before_sha:
        guards._finish_noop_auto_rebase(context)
        return

    dirty_files = probes._worktree_dirty_files(context.worktree)
    if dirty_files:
        guards._park_dirty_auto_rebase(context, before_sha, dirty_files)
        return

    branch = paths._resolve_branch_name(
        context.state, context.spec, context.issue.number,
    )
    if not authentication._push_branch(
        context.spec,
        context.worktree,
        branch,
        force_with_lease=before_sha or None,
    ):
        guards._park_failed_auto_rebase_push(context, before_sha, branch)
        return
    _finalize_auto_rebase(context, branch, after_sha)
