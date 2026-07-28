# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One `resolving_conflict` tick, in the order its questions have to be asked.

The pinned `pr_number` is read first because everything below it needs the PR;
without one the label can only have come from a manual relabel, so the tick
parks once and waits rather than guessing which branch to rebase. The terminal
arcs come next and outrank the rebase entirely: a PR a human merged after
resolving the conflicts by hand, or one they closed, is the answer to every
question the loop would otherwise ask.

The body-edit check sits between the terminals and the rebase because an edit
changes what "resolved" means -- the dev has to see the new body before deciding
whether its in-flight resolution still applies. A pushed answer hands back to
`validating`; a bare acknowledgement stays here rather than parking, so a
harmless clarification does not stall the rebase.

The manually-closed arc has one known gap: once a PR-still-open issue is
flipped to `rejected`, nothing observes a later PR close -- the dispatcher's
terminal branch is a no-op and the polling sweep only picks up closed issues
still labeled `in_review` / `resolving_conflict`. For the "close the issue
first, then the PR" ordering the operator cleans up the worktree, the local
branch, and the remote branch by hand.
"""
from __future__ import annotations

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.workflow.engine import drift as _drift
from orchestrator.workflow.engine import terminals as _terminals
from orchestrator.workflow.stages.conflicts import models as _models
from orchestrator.workflow.stages.conflicts import resume as _resume
from orchestrator.workflow.stages.conflicts import routing as _routing
from orchestrator.workflow.stages.conflicts import transitions as _transitions


def _handle_resolving_conflict(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue
) -> None:
    """Drive an unmergeable PR back to mergeable.

    Rebase the per-issue branch onto `origin/<base>`. On a clean rebase
    that actually moved HEAD, push and flip to `validating` so the
    reviewer re-runs against the rebased tree; if the base hasn't moved
    (branch already up-to-date) skip the push and flip straight to
    `validating` too. On real content conflicts, resume the dev session
    on the locked backend with a conflict-resolution prompt, push the
    resolved commit, and likewise flip to `validating`. Docs do not run
    here: the single docs pass runs after the reviewer's final
    `VERDICT: APPROVED` handoff to `documenting` in
    `_handle_validating`, so every pushed conflict-resolution path
    targets `validating` directly. Cap loops via `MAX_CONFLICT_ROUNDS`
    (parks awaiting human on exhaustion). On agent timeout / dirty
    tree / push failure, park awaiting human and let the operator
    unstick.

    Rebasing rewrites commit SHAs, so every pushed rebase resets
    `review_round`; validation must re-approve the rebased branch before
    any merge gate can pass.
    """
    state = gh.read_pinned_state(issue)
    ctx = _models._ConflictContext(gh, spec, issue, state)
    pr_number = state.get("pr_number")

    if pr_number is None:
        _park_conflict_missing_pr_number(ctx)
        return

    pr = gh.get_pr(int(pr_number))

    # Drain the shared PR/issue terminal arcs (merged PR -> `done`,
    # closed PR -> `rejected`, open PR + manually-closed issue ->
    # `rejected` without branch cleanup). The merged branch fires for
    # both "human merged after resolving conflicts manually" and
    # "Resolves #N auto-closed the issue when the PR merged"; the
    # open-PR + closed-issue arc only fires for issues a human closed
    # directly.
    if _terminals._drain_review_pr_terminals(
        gh, spec, issue, state, pr, stage="resolving_conflict",
    ):
        return

    # User-content drift: a human edited the issue body while the dev
    # was resolving conflicts. Resuming with the new body+comments lets
    # the dev decide whether the edit affects the conflict resolution.
    # On a successful pushed fix we hand straight to `validating` so the
    # reviewer re-runs against the updated tree; the docs pass is
    # deferred to the single post-approval hop. On an ack (no commit
    # but a reply) we stay in `resolving_conflict` without parking so a
    # harmless clarification doesn't stall the rebase.
    new_hash = _drift._detect_user_content_change(gh, issue, state)
    if new_hash is not None:
        _resume._resume_on_user_content_change(ctx, pr_number, new_hash)
        return

    _routing._drive_conflict_rebase(ctx, pr, pr_number)


def _park_conflict_missing_pr_number(ctx: _models._ConflictContext) -> None:
    """Park a `resolving_conflict` issue that carries no pinned `pr_number`.

    Reaching here means a manual relabel from outside the normal route; the
    rebase / push paths all need the PR. An already-parked issue is left alone
    so the park comment is not re-posted every tick.
    """
    if ctx.state.get("awaiting_human"):
        return
    _transitions._park_conflict(
        ctx,
        f"{config.HITL_MENTIONS} `resolving_conflict` without a pinned "
        "`pr_number`; manual relabeling suspected. Set the workflow "
        "label back to `validating` after fixing.",
        reason="missing_pr_number",
    )
