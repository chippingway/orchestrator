# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two ways a rebase attempt ends, and what each publishes.

A clean rebase has three exits and the dirty check gates all of them, including
the one that pushes nothing. A no-op flip carries the worktree into
`validating` untouched, where the reviewer agent reads the tree directly -- so
an uncommitted edit left by a tick that crashed before its own dirty check
would put the reviewer's vote against content the PR does not have, and the
in_review ready-ping would then advertise that approval to a human merger.

The no-op flip still bumps `conflict_round`. Nothing was resolved, but PyGithub
cannot tell a content conflict from a PR blocked by branch protection or
required reviewers, so without counting the no-op an unmergeable-for-other-
reasons PR would bounce between `in_review` and `resolving_conflict` forever
with the cap never firing.

Real content conflicts go to the dev instead, and the push that follows is
leased against the pre-rebase HEAD: the agent rewrote history from that SHA, so
that is the only remote state the force-push may legitimately replace.
"""
from __future__ import annotations

from pathlib import Path

from orchestrator import config
from orchestrator._workflow_state import log
from orchestrator.git import authentication as _authentication
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.workflow.engine import prompts as _prompts
from orchestrator.workflow.stages.conflicts import models as _models
from orchestrator.workflow.stages.conflicts import outcomes as _outcomes
from orchestrator.workflow.stages.conflicts import resume as _resume
from orchestrator.workflow.stages.conflicts import state as _state
from orchestrator.workflow.stages.conflicts import transitions as _transitions
from orchestrator.workflow.state import WorkflowLabel


def _publish_clean_rebase(
    ctx: _models._ConflictContext,
    wt: Path,
    before_sha: str,
    conflict_round: int,
    pr_number,
) -> None:
    """Dispose of a clean `git rebase <remote>/<base>` outcome.

    Parks on a dirty tree; flips to `validating` without a push when the
    base had not moved (no-op rebase, still counted against the cap); or
    force-pushes the rebased head and flips to `validating`. The caller
    returns immediately after; every exit writes pinned state.
    """
    spec = ctx.spec
    # Dirty check before EITHER clean-rebase exit (no-op flip OR rebased-head
    # push): a pre-existing uncommitted edit (left by a previous tick that
    # crashed before its own dirty check ran) would otherwise survive a no-op
    # flip into validating, where the reviewer agent reads the worktree
    # directly. The reviewer would then vote on a tree that does NOT match the
    # PR head; the in_review HITL ready-ping would later advertise the PR as
    # ready for human merge with the reviewer's approval sitting against an
    # incorrect SHA, inviting a human merge over unreviewed content. Park
    # rather than push or flip, mirroring `_on_dirty_worktree`'s "refuse to
    # publish an incomplete branch" rule.
    dirty = _verification_probes._worktree_dirty_files(wt)
    if dirty:
        _transitions._park_conflict(
            ctx,
            f"{config.HITL_MENTIONS} worktree has {len(dirty)} "
            f"uncommitted change(s) after `git rebase "
            f"{spec.remote_name}/{spec.base_branch}`; refusing to "
            "push or hand back to validating with a dirty tree.",
            reason="dirty_worktree",
        )
        return
    after_sha = _verification_probes._head_sha(wt)
    if not after_sha or after_sha == before_sha:
        _flip_base_up_to_date(ctx, conflict_round, pr_number, after_sha)
        return
    if not _authentication._push_branch(
        spec, wt,
        _worktree_paths._resolve_branch_name(ctx.state, spec, ctx.issue.number),
        force_with_lease=before_sha or None,
    ):
        _transitions._park_conflict(
            ctx,
            f"{config.HITL_MENTIONS} git push failed after auto-rebasing "
            f"`{spec.remote_name}/{spec.base_branch}`; "
            "see orchestrator logs.",
            reason="push_failed",
        )
        return
    # Pushed branch diff -> hand straight back to validating; the single docs
    # pass runs after final reviewer approval.
    _transitions._hand_resolved_round_to_validating(
        ctx, conflict_round, pr_number,
        outcome="base_rebased_clean", sha=after_sha,
    )


def _flip_base_up_to_date(
    ctx: _models._ConflictContext, conflict_round: int, pr_number, after_sha,
) -> None:
    """Hand a no-op base rebase (branch already current) back to `validating`.

    Increments `conflict_round` even though no diff was applied: an unmergeable
    PR blocked purely by branch protection / required reviewers (PyGithub
    cannot tell those from a content conflict) would otherwise loop
    in_review <-> resolving_conflict forever with the cap never firing.
    Counting the no-op against the cap surfaces it within MAX_CONFLICT_ROUNDS
    ticks. Does NOT stamp `last_conflict_resolved_at` -- nothing was resolved.
    """
    log.info(
        "issue=#%d resolving_conflict: branch already up-to-date with %s/%s",
        ctx.issue.number, ctx.spec.remote_name, ctx.spec.base_branch,
    )
    ctx.state.set(_state._REVIEW_ROUND, 0)
    ctx.state.set(_state._CONFLICT_ROUND, conflict_round + 1)
    _transitions._emit_conflict_round_incremented(
        ctx,
        pr_number=int(pr_number),
        new_round=conflict_round + 1,
        outcome="base_up_to_date",
        sha=after_sha,
    )
    ctx.gh.set_workflow_label(ctx.issue, WorkflowLabel.VALIDATING)
    ctx.gh.write_pinned_state(ctx.issue, ctx.state)


def _resolve_conflicts_with_agent(
    ctx: _models._ConflictContext,
    conflicted_files,
    before_sha: str,
    conflict_round: int,
) -> None:
    """Resume the dev session to resolve real rebase content conflicts.

    Builds the conflict-resolution prompt from the conflicted files,
    resumes the locked backend, and funnels the result through
    `_post_conflict_resolution_result` (leasing the push against
    `before_sha`). Returns without touching durable state when a live
    pause lands mid-run.
    """
    spec = ctx.spec
    fix_prompt = _prompts._build_conflict_resolution_prompt(
        f"{spec.remote_name}/{spec.base_branch}", conflicted_files,
    )
    run = _resume._run_conflict_resume(ctx, fix_prompt)
    # Live pause applied mid-run: return before
    # `_post_conflict_resolution_result` pushes / relabels / writes pinned
    # state -- the resolved commit stays on the branch until the label is
    # removed.
    if run.paused:
        return
    _outcomes._post_conflict_resolution_result(
        ctx, run, before_sha, conflict_round,
        force_with_lease=before_sha or None,
    )
