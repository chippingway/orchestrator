# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One validating tick, in the order its questions have to be asked.

The terminals come first because a PR a human already merged, or an issue
closed without one, makes the whole round pointless -- and running the
reviewer against a branch that landed would pull a finished issue back into
the loop. Drift comes next, ahead of the awaiting-human branch, because a body
edit mid-review means the work under review is answering the wrong
requirements; the three parks that defer back out of it are the ones whose
reply belongs to the reviewer or to the operator's round-cap command instead
of to the dev.

The awaiting-human branch then either finishes the tick or clears the park
into a fresh reviewer round, which is why it answers in words rather than a
bool: `"return"` means handled, and `"spawn_reviewer"` means fall through to
the round-cap check and the spawn below.
"""
from __future__ import annotations

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import terminals as _terminals
from orchestrator.workflow.stages.validating import awaiting_resume as _awaiting_resume
from orchestrator.workflow.stages.validating import drift as _drift
from orchestrator.workflow.stages.validating import reviewer as _reviewer
from orchestrator.workflow.stages.validating import state as _state


def _finalize_validating_terminal(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> bool:
    """Terminal short-circuits checked before the reviewer runs; True when one
    fired and the caller must return.

    External merge: a human merged the PR while the reviewer was queued.
    Finalize to `done` rather than running the reviewer against a branch that
    already landed. Closed-issue counterpart: the closed-`validating` sweep
    yields issues a human closed without a merged PR (the change was rejected
    mid-review, or the PR was closed-without-merge); flip to `rejected` so the
    reviewer does not spawn against a closed issue and the PR is not relabeled
    back to `in_review`. The in_review / fixing handlers carry equivalent
    terminal checks.
    """
    if _terminals._finalize_if_pr_merged(gh, spec, issue, state):
        return True
    return _terminals._finalize_if_issue_closed(gh, spec, issue, state)


def _handle_validating(gh: GitHubClient, spec: config.RepoSpec, issue: Issue) -> None:
    state = gh.read_pinned_state(issue)
    pr_number = state.get("pr_number")

    if _finalize_validating_terminal(gh, spec, issue, state):
        return

    # User-content drift resume runs before the awaiting-human and reviewer
    # branches: a body edit mid-review must resume the dev on the new body
    # rather than re-review stale work. Returns True when it fully handled the
    # tick; a reviewer-side (`reviewer_timeout` / `reviewer_failed`) or
    # `review_cap` park defers to the awaiting-human branch below (that branch
    # owns the human's "retry" / `/orchestrator add-review-rounds` comment).
    if _drift._resume_dev_on_validating_drift(gh, spec, issue, state):
        return

    # Awaiting-human path: human replied after a park (or a transient
    # condition self-resolved). The helper resumes the dev on their feedback,
    # recovers transient parks silently, or clears a reviewer-side / review-cap
    # park into a reviewer re-run. "return" -> the tick is fully handled;
    # "spawn_reviewer" -> fall through to the round-cap check and reviewer
    # spawn below.
    if state.get("awaiting_human"):
        outcome = _awaiting_resume._handle_validating_awaiting_human(gh, spec, issue, state)
        if outcome == _state._OUTCOME_RETURN:
            return

    reviewer_run = _reviewer._run_reviewer_round(gh, spec, issue, state, pr_number)
    if reviewer_run is None:
        return

    _reviewer._dispatch_reviewer_result(gh, spec, issue, state, reviewer_run)
