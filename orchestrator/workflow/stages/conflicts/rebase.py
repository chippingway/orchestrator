# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The rebase itself, and the two fetches that have to precede it.

Both fetches go through the hardened authenticated path rather than a plain
`git fetch`, and both park on failure instead of proceeding: measuring a
worktree against a stale `<remote>/<branch>` ref would report a branch someone
else pushed to as in-sync, and rebasing onto a stale `<remote>/<base>` would
produce a branch that is already behind the moment it lands.

`merge_attempt` is emitted for every attempt including the failures, because
the audit trail of what the base rebase did is the record an operator reads
when a PR keeps bouncing back here. The disposition after it splits three ways:
a clean rebase publishes, a failure that named no conflicted files parks
(without files there is nothing to hand a dev), and real content conflicts go
to the agent.
"""
from __future__ import annotations

import logging
from pathlib import Path

from orchestrator import config
from orchestrator.git import authentication as _authentication
from orchestrator.git.base_sync import pre_pr as _base_sync_pre_pr
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.workflow.stages.conflicts import models as _models
from orchestrator.workflow.stages.conflicts import publication as _publication
from orchestrator.workflow.stages.conflicts import state as _state
from orchestrator.workflow.stages.conflicts import transitions as _transitions

log = logging.getLogger("orchestrator.workflow")


def _fetch_pr_branch(
    ctx: _models._ConflictContext, wt: Path, branch: str,
) -> bool:
    """Fetch `<remote>/<branch>` into the worktree. Returns False (after
    parking) on fetch failure, True otherwise."""
    spec = ctx.spec
    fetch_branch = _authentication._authed_fetch(
        spec,
        f"+refs/heads/{branch}:refs/remotes/{spec.remote_name}/{branch}",
        cwd=wt,
    )
    if fetch_branch.returncode == 0:
        return True
    log.error(
        "issue=#%d branch fetch failed in resolving_conflict: %s",
        ctx.issue.number, (fetch_branch.stderr or "").strip(),
    )
    _transitions._park_conflict(
        ctx,
        f"{config.HITL_MENTIONS} `git fetch {spec.remote_name} {branch}` "
        "failed during conflict resolution; see orchestrator logs.",
        reason="fetch_failed",
    )
    return False


def _fetch_base_ref(ctx: _models._ConflictContext, wt: Path) -> bool:
    """Fetch `<remote>/<base>` into the worktree. Returns False (after
    parking) on fetch failure, True otherwise."""
    spec = ctx.spec
    fetch_base = _authentication._authed_fetch(
        spec,
        f"+refs/heads/{spec.base_branch}:"
        f"refs/remotes/{spec.remote_name}/{spec.base_branch}",
        cwd=wt,
    )
    if fetch_base.returncode == 0:
        return True
    log.error(
        "issue=#%d base fetch failed in resolving_conflict: %s",
        ctx.issue.number, (fetch_base.stderr or "").strip(),
    )
    _transitions._park_conflict(
        ctx,
        f"{config.HITL_MENTIONS} "
        f"`git fetch {spec.remote_name} {spec.base_branch}` "
        "failed during conflict resolution; see orchestrator logs.",
        reason="fetch_failed",
    )
    return False


def _rebase_and_dispose(
    ctx: _models._ConflictContext, pr_number, conflict_round: int, wt: Path,
) -> None:
    """Rebase the worktree onto base, emit `merge_attempt`, and dispose.

    A clean rebase routes to `_publish_clean_rebase`; a rebase that failed
    without listing conflicted files parks; real content conflicts hand to
    `_resolve_conflicts_with_agent`.
    """
    spec = ctx.spec
    before_sha = _verification_probes._head_sha(wt)
    succeeded, conflicted_files = _base_sync_pre_pr._rebase_base_into_worktree(
        spec, wt,
    )
    ctx.gh.emit_event(
        "merge_attempt",
        issue_number=ctx.issue.number,
        stage="resolving_conflict",
        pr_number=int(pr_number),
        sha=before_sha or None,
        method="base_rebase",
        result=_merge_result(succeeded, conflicted_files),
        conflict_round=conflict_round,
        review_round=int(ctx.state.get(_state._REVIEW_ROUND) or 0),
        retry_count=ctx.state.get("retry_count"),
    )

    if succeeded:
        _publication._publish_clean_rebase(
            ctx, wt, before_sha, conflict_round, pr_number,
        )
        return

    if not conflicted_files:
        _transitions._park_conflict(
            ctx,
            f"{config.HITL_MENTIONS} "
            f"`git rebase {spec.remote_name}/{spec.base_branch}` "
            "failed without listing conflicted files; manual intervention "
            "needed.",
            reason="rebase_failed_no_files",
        )
        return

    _publication._resolve_conflicts_with_agent(
        ctx, conflicted_files, before_sha, conflict_round,
    )


def _merge_result(succeeded: bool, conflicted_files) -> str:
    """Map a base-rebase outcome to the `merge_attempt` event's `result`."""
    if succeeded:
        return "success"
    return "conflict" if conflicted_files else "failed"
