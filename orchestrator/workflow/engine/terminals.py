# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How an issue stops being worked.

Three conditions end one: the linked PR merged (`done`), the linked PR closed
without merging (`rejected`), and a human closed the issue while its PR is
still open (`rejected` too -- a human stop signal outranks whatever the stage
was about to do). What the three share is the tail, not the condition that
reaches them: each stamps its terminal timestamp, flips to a terminal label,
posts the cumulative usage receipt, and writes pinned state once. That shared
tail is why they sit together -- an arc added beside them inherits the order
rather than reinventing it.

Two entry points reach the arcs, and they differ only in who fetched the PR.
`_drain_review_pr_terminals` serves the stages already holding one --
`in_review`, `fixing`, `resolving_conflict` -- and tries all three arcs against
the PR the caller passes; `pr=None` is a deliberate no-op so `fixing` can hand
over its own fetch failure unchanged. `_finalize_if_pr_merged` and
`_finalize_if_issue_closed` serve the stages that hold no PR at handler entry
-- `implementing`, `documenting`, `validating`, plus the umbrella / blocked
child aggregation -- and each fetches its own, which is also why each owns a
fetch-failure answer: the merged check leaves the issue alone, the closed-issue
check defers the whole tick so a transient failure cannot label a merged-PR
issue `rejected`. Every entry point returns True to mean "this tick is over".

`workflow/stages/discussion/terminal.py` composes the arcs itself rather than
taking an entry point here, because its third one differs: a closed issue whose
plan PR is still open KEEPS its label -- that label is what the closed-issue
sweep finds it by, and the plan the humans are reading is what decides. It
reaches `_finalize_merged_pr` and `_finalize_rejected_pr` directly for that
reason, and `_finalize_closed_issue_with_open_pr` for a close with no pull
request to poll at all -- which is the same shape that arc already serves here,
a close whose linked PR is not the thing being decided. It records as fully as
the other two -- the stamp, the `rejected` label, the receipt, one write -- and
differs only in what it has nothing to say about: no event, since there is no
pull request for the payload to name, and no branch cleanup.

Branch cleanup is deliberately outside the shared tail. It runs on the two arcs
where the PR itself is gone and the branch is dead weight, and is withheld on
the open-PR arc so an operator can still reopen or salvage what the closed
issue left behind. That arc emits no `pr_closed_without_merge` for the same
reason -- the PR has not closed yet -- while the closed-issue entry point does
emit one once it confirms the linked PR is closed as well.

The receipt's position in the tail is a contract, not a preference: it is
posted BEFORE the write so its comment id rides the same persisted state and a
later drift or watermark tick reads it as orchestrator-authored.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from github.Issue import Issue

from orchestrator import config
from orchestrator.git.worktrees import terminal as _worktree_terminal
from orchestrator.git.worktrees.paths import _resolve_branch_name
from orchestrator.github.client import GitHubClient
from orchestrator.github.issues import (
    _ISSUE_STATE_CLOSED,
    _ISSUE_STATE_OPEN,
    _STATE_ATTR,
)
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import usage as _usage
from orchestrator.workflow.state import WorkflowLabel, stage_name

log = logging.getLogger("orchestrator.workflow")


def _finalize_if_pr_merged(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> bool:
    """Flip the issue to `done` when its linked PR has already merged.

    Mirrors the terminal-merge arc in `_handle_in_review` / `_handle_fixing`
    / `_handle_resolving_conflict` so the same finalize path can fire from
    any stage. Used by the handlers that carry no merged-PR arc of their own
    (`_handle_implementing`, `_handle_documenting`, `_handle_validating`)
    and by the umbrella / blocked aggregation when a child PR was merged
    externally but the child's workflow label was never advanced past the
    in-flight stage -- the umbrella's all-`done` aggregation would
    otherwise wait forever for that stale child.

    Returns True when the helper finalized the issue (caller must return
    immediately); False when there is nothing to do (no `pr_number`, PR
    fetch failed, or PR is not merged).
    """
    pr_number = state.get("pr_number")
    if pr_number is None:
        return False
    try:
        pr = gh.get_pr(int(pr_number))
    except Exception:
        log.exception(
            "issue=#%s could not fetch PR #%s while checking for "
            "external merge; leaving alone", issue.number, pr_number,
        )
        return False
    if gh.pr_state(pr) != "merged":
        return False
    _finalize_merged_pr(
        _ReviewTerminalContext(
            gh=gh,
            spec=spec,
            issue=issue,
            state=state,
            pr=pr,
            stage=stage_name(gh.workflow_label(issue)),
        ),
        close_error="could not close after detecting external merge",
        close_if_open_only=True,
    )
    return True


@dataclass(frozen=True)
class _ReviewTerminalContext:
    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    pr: Any
    stage: str | None

    @property
    def pr_number(self) -> int:
        return int(self.state.get("pr_number"))

    @property
    def conflict_round(self):
        conflict_round = self.state.get("conflict_round")
        if self.stage == "resolving_conflict":
            return int(conflict_round or 0)
        return conflict_round


def _close_terminal_issue(
    context: _ReviewTerminalContext, error_message: str,
) -> None:
    try:
        context.issue.edit(state=_ISSUE_STATE_CLOSED)
    except Exception:
        log.exception(
            "issue=#%s %s", context.issue.number, error_message,
        )


def _cleanup_review_terminal(context: _ReviewTerminalContext) -> None:
    _worktree_terminal._cleanup_terminal_branch(
        context.gh,
        context.spec,
        context.issue.number,
        branch=_resolve_branch_name(
            context.state, context.spec, context.issue.number,
        ),
    )


def _finalize_merged_pr(
    context: _ReviewTerminalContext,
    *,
    close_error: str,
    close_if_open_only: bool = False,
) -> None:
    context.state.set("merged_at", _usage._now_iso())
    context.gh.set_workflow_label(context.issue, WorkflowLabel.DONE)
    _usage._post_issue_usage_verdict(context.gh, context.issue, context.state)
    context.gh.write_pinned_state(context.issue, context.state)
    context.gh.emit_event(
        "pr_merged",
        issue_number=context.issue.number,
        stage=context.stage,
        pr_number=context.pr_number,
        sha=getattr(context.pr.head, "sha", None) or None,
        merge_method="external",
        review_round=int(context.state.get("review_round") or 0),
        conflict_round=context.conflict_round,
        retry_count=context.state.get("retry_count"),
    )
    if (
        not close_if_open_only
        or getattr(context.issue, _STATE_ATTR, _ISSUE_STATE_OPEN) != _ISSUE_STATE_CLOSED
    ):
        _close_terminal_issue(context, close_error)
    _cleanup_review_terminal(context)


def _finalize_rejected_pr(context: _ReviewTerminalContext) -> None:
    context.state.set("closed_without_merge_at", _usage._now_iso())
    context.gh.set_workflow_label(context.issue, WorkflowLabel.REJECTED)
    _usage._post_issue_usage_verdict(context.gh, context.issue, context.state)
    context.gh.write_pinned_state(context.issue, context.state)
    context.gh.emit_event(
        "pr_closed_without_merge",
        issue_number=context.issue.number,
        stage=context.stage,
        pr_number=context.pr_number,
        sha=getattr(context.pr.head, "sha", None) or None,
        review_round=int(context.state.get("review_round") or 0),
        conflict_round=context.conflict_round,
        retry_count=context.state.get("retry_count"),
    )
    _close_terminal_issue(context, "could not close after reject")
    _cleanup_review_terminal(context)


def _finalize_closed_issue_with_open_pr(context: _ReviewTerminalContext) -> None:
    context.state.set("closed_without_merge_at", _usage._now_iso())
    context.gh.set_workflow_label(context.issue, WorkflowLabel.REJECTED)
    _usage._post_issue_usage_verdict(context.gh, context.issue, context.state)
    context.gh.write_pinned_state(context.issue, context.state)


def _drain_review_terminal(context: _ReviewTerminalContext) -> bool:
    if context.pr is None:
        return False
    pr_status = context.gh.pr_state(context.pr)
    if pr_status == "merged":
        _finalize_merged_pr(context, close_error="could not close after merge")
        return True
    if pr_status == _ISSUE_STATE_CLOSED:
        _finalize_rejected_pr(context)
        return True
    if getattr(context.issue, _STATE_ATTR, _ISSUE_STATE_OPEN) == _ISSUE_STATE_CLOSED:
        _finalize_closed_issue_with_open_pr(context)
        return True
    return False


def _drain_review_pr_terminals(
    gh: GitHubClient,
    *context_args,
    stage: str,
) -> bool:
    """Drain the three PR/issue terminal arcs shared by `_handle_in_review`,
    `_handle_fixing`, and `_handle_resolving_conflict`.

    Caller passes the already-fetched PR and its own `stage` label. Each
    stage owns its fetch-failure semantics: `in_review` and
    `resolving_conflict` let `gh.get_pr` exceptions propagate to
    `_process_issue`'s catch; `fixing` catches and bails with `pr=None`
    so the rest of its handler can short-circuit. Passing `pr=None` here
    is a no-op (returns False) so fixing's deferral arrives unchanged.

    Three arcs:

      1. `pr_state == "merged"`: stamp `merged_at`, flip to `done`,
         write state, emit `pr_merged` (`merge_method="external"`),
         close the issue if still open, and clean up the branch.
      2. `pr_state == "closed"` (unmerged): stamp
         `closed_without_merge_at`, flip to `rejected`, write state,
         emit `pr_closed_without_merge`, close the issue if still open,
         and clean up the branch.
      3. Issue is closed but PR is still open (the closed-issue sweep
         surfaced a human stop signal): stamp
         `closed_without_merge_at`, flip to `rejected`, write state.
         Deliberately no event emit (the PR is still open and may be
         reopened/salvaged) and no branch cleanup (the operator may
         want the open PR's history).

    Returns True when an arc fired (caller must return immediately).
    Returns False when none fired (caller continues with the same `pr`).
    """
    spec, issue, state, pr = context_args
    return _drain_review_terminal(
        _ReviewTerminalContext(gh, spec, issue, state, pr, stage),
    )


@dataclass(frozen=True)
class _ClosedIssuePR:
    number: int | None
    pr: Any = None
    defer: bool = False


def _closed_issue_pr(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> _ClosedIssuePR:
    raw_number = state.get("pr_number")
    if raw_number is None:
        return _ClosedIssuePR(number=None)
    number = int(raw_number)
    try:
        pr = gh.get_pr(number)
    except Exception:
        log.exception(
            "issue=#%s could not fetch PR #%s while finalizing a "
            "closed issue; deferring (next tick retries the "
            "merged-PR path)", issue.number, raw_number,
        )
        return _ClosedIssuePR(number=number, defer=True)
    return _ClosedIssuePR(
        number=number,
        pr=pr,
        defer=gh.pr_state(pr) == "merged",
    )


def _emit_closed_pr_rejection(context: _ReviewTerminalContext) -> None:
    context.gh.emit_event(
        "pr_closed_without_merge",
        issue_number=context.issue.number,
        stage=context.stage,
        pr_number=context.pr_number,
        sha=getattr(context.pr.head, "sha", None) or None,
        review_round=int(context.state.get("review_round") or 0),
        conflict_round=context.state.get("conflict_round"),
        retry_count=context.state.get("retry_count"),
    )
    _cleanup_review_terminal(context)


def _finalize_if_issue_closed(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> bool:
    """Flip a closed-but-not-merged issue to `rejected`.

    Pairs with `_finalize_if_pr_merged`: that helper drains the merged-PR
    arc, this one drains the closed-issue counterpart so closed issues
    yielded by the `implementing` / `documenting` / `validating` sweep
    entries do NOT spawn the dev / docs / reviewer agent, push to
    the per-issue branch, or post on the now-closed issue thread.
    `_handle_in_review` / `_handle_fixing` carry equivalent guards
    inline via their PR-state arcs; callers in the sweep stages
    invoke this helper right after `_finalize_if_pr_merged` so the
    merged case is drained first and only the rejected case lands here.

    Branch cleanup follows the in_review / fixing convention: only when
    the linked PR itself is also closed (a closed PR without merge is
    `pr_closed_without_merge`-emit territory and the branch is dead
    weight). An open PR with a manually-closed issue is left alone so
    the operator can salvage / reopen it; the orchestrator-owned branch
    and worktree stay until the PR closes.

    Returns True when the caller must NOT continue the handler this
    tick: the issue was finalized to `rejected`, OR the issue is closed
    but the linked PR state could not be confirmed yet (deferred to a
    later tick so a transient fetch failure cannot permanently mis-
    label a merged-PR issue, AND so the closed issue is not driven
    through normal dev / docs / reviewer work). Returns False only
    when the issue is still open and the handler should proceed.
    """
    if getattr(issue, _STATE_ATTR, _ISSUE_STATE_OPEN) != _ISSUE_STATE_CLOSED:
        return False
    linked_pr = _closed_issue_pr(gh, issue, state)
    if linked_pr.defer:
        return True
    context = _ReviewTerminalContext(
        gh, spec, issue, state, linked_pr.pr,
        stage_name(gh.workflow_label(issue)),
    )
    _finalize_closed_issue_with_open_pr(context)
    if linked_pr.pr is not None and gh.pr_state(linked_pr.pr) == _ISSUE_STATE_CLOSED:
        _emit_closed_pr_rejection(context)
    return True
