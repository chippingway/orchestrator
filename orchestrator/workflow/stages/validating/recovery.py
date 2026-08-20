# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The parks that can clear without anyone commenting.

A push that lost a race and an agent killed by its own timeout are both
conditions the next tick can simply re-attempt, but neither produces the human
reply the awaiting-human resume waits for. Without a silent retry the issue
sits parked forever on a failure that already went away.

So the recovery runs quietly and answers in one of three words. It must not
spawn an agent or post anything -- the caller owns the visible side, so a tick
that is still stuck produces no churn at all. It IS allowed to move the review
round, and it is the only writer permitted to while the park flags are still
set: a timeout that had already committed gets its push finished here, and
that landed commit is a head the reviewer has not seen.

`push_failed` and `agent_timeout` are the two that actually touch git;
the reviewer-side reasons clear on sight, because there is no dev work to
finish, only a reviewer to re-spawn. Every probe fails closed to `"stuck"` --
a missing worktree, a dirty tree, an unreadable `pre_dev_fix_sha`, a push that
fails again -- since leaving the park standing costs a poll and publishing
blind costs the PR.

`_recovery_followup_comment` is the one sentence a healed park owes the thread,
and it is decided here because the pair it is keyed by -- the reason parked and
the word the probe answered with -- is this module's own vocabulary. Choosing
the text is all that happens: the caller that clears the flags is what posts
it, so the probe stays as quiet as its contract says and a tick that is still
stuck still says nothing at all. The mention that filed the park is what earns
the reply, so a park with no `last_action_comment_id` behind it answers None --
nothing was said, so nothing needs taking back -- and so does a reason/outcome
pair the table does not name, rather than guess at wording for it.

"At most once per episode" is answered from the thread rather than from pinned
state, because the post and the write that clears the park cannot be made one
operation: a process that dies between them leaves GitHub holding a comment
that no local record knows about, and any receipt written beside the clear
dies with it. So the follow-up carries `_RECOVERY_FOLLOWUP_MARKER` and the next
attempt looks for it among the comments past `last_action_comment_id` -- the
park's own mention id, which is what scopes the search to THIS episode, since a
later park stamps a higher watermark and cannot be silenced by an older
follow-up sitting below it. A forged marker costs its author the notification
they would have been spared anyway, which is why the cheap check is the right
one here.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Optional

from github.Issue import Issue

from orchestrator import config
from orchestrator.git import authentication as _authentication
from orchestrator.git.verification import probes as _verification_probes
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.stages.validating import dev_fix as _dev_fix
from orchestrator.workflow.stages.validating import state as _state

# Stamped on every follow-up so a later tick can recognize one it posted even
# when the pinned write that was supposed to record it never landed. An HTML
# comment, so it is invisible in the rendered issue thread.
_RECOVERY_FOLLOWUP_MARKER = "<!--orchestrator-recovery-followup-->"

_LAST_ACTION_COMMENT_ID = "last_action_comment_id"

# The clause each (park reason, recovery outcome) pair earns in the follow-up.
# Keyed by both because the same word means different work depending on what
# parked: a `pushed` that finishes a `push_failed` is the retry the operator
# was pinged about, while a `pushed` that finishes an `agent_timeout` is a
# commit the killed run had already made.
_RECOVERY_DETAILS = MappingProxyType({
    (_state._REASON_PUSH_FAILED, _state._OUTCOME_PUSHED):
        "the failed push was retried and succeeded",
    (_state._REASON_AGENT_TIMEOUT, _state._OUTCOME_PUSHED):
        "the commit the timed-out run had already made was pushed",
    (_state._REASON_AGENT_TIMEOUT, _state._OUTCOME_CLEARED):
        "the timed-out run had left nothing to publish",
    (_state._REASON_REVIEWER_TIMEOUT, _state._OUTCOME_CLEARED):
        "the reviewer is being re-spawned",
    (_state._REASON_REVIEWER_FAILED, _state._OUTCOME_CLEARED):
        "the reviewer is being re-spawned",
})


def _recover_failed_push(
    spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> str:
    worktree = _worktree_paths._worktree_path(spec, issue.number)
    if not worktree.exists():
        return _state._OUTCOME_STUCK
    branch = _worktree_paths._resolve_branch_name(state, spec, issue.number)
    if not _authentication._push_branch(spec, worktree, branch):
        return _state._OUTCOME_STUCK
    _dev_fix._bump_review_round(state)
    return _state._OUTCOME_PUSHED


def _recover_timed_out_fix(
    spec: config.RepoSpec, issue: Issue, state: PinnedState,
) -> str:
    worktree = _worktree_paths._worktree_path(spec, issue.number)
    if (
        not worktree.exists()
        or _verification_probes._worktree_dirty_files(worktree)
    ):
        return _state._OUTCOME_STUCK
    before_sha = state.get(_state._PRE_DEV_FIX_SHA)
    if not isinstance(before_sha, str):
        return _state._OUTCOME_STUCK
    current_sha = _verification_probes._head_sha(worktree)
    if not current_sha or current_sha == before_sha:
        state.set(_state._PRE_DEV_FIX_SHA, None)
        return _state._OUTCOME_CLEARED
    branch = _worktree_paths._resolve_branch_name(state, spec, issue.number)
    if not _authentication._push_branch(spec, worktree, branch):
        return _state._OUTCOME_STUCK
    state.set(_state._PRE_DEV_FIX_SHA, None)
    _dev_fix._bump_review_round(state)
    return _state._OUTCOME_PUSHED


def _try_recover_validating_transient_park(
    spec: config.RepoSpec, issue: Issue, state: PinnedState
) -> str:
    """Quietly attempt to clear a transient validating park.

    Returns one of:
      * ``"stuck"`` -- the underlying condition has not resolved; caller
        leaves the park flags in place and returns silently.
      * ``"cleared"`` -- the park can be cleared, but nothing new
        landed on the PR (reviewer-only crash, or a dev-timeout that
        had not actually produced a commit). Caller clears the flags
        and stays on `validating` so the reviewer reruns.
      * ``"pushed"`` -- a dev fix was finished off during recovery
        (a deferred push of `push_failed`, or the trailing push of an
        `agent_timeout` that had committed before being killed).
        Caller clears the flags, resets stale approval state, and
        stays on `validating` so the reviewer re-evaluates the new
        head.

    Must not spawn the agent or post issue/PR comments -- the caller owns
    the visible side of the recovery so a still-stuck tick produces no
    churn.

    The helper IS allowed to update review-round bookkeeping when a fix
    landed during recovery (e.g. an agent_timeout where the dev had
    actually committed before timing out, and we finish the push here).
    Callers should not mutate the round themselves; this is the only
    write path while the park flags are still set.
    """
    park_reason = state.get(_state._PARK_REASON)
    if park_reason == _state._REASON_PUSH_FAILED:
        return _recover_failed_push(spec, issue, state)
    if park_reason in (_state._REASON_REVIEWER_TIMEOUT, _state._REASON_REVIEWER_FAILED):
        return _state._OUTCOME_CLEARED
    if park_reason == _state._REASON_AGENT_TIMEOUT:
        return _recover_timed_out_fix(spec, issue, state)
    return _state._OUTCOME_STUCK


def _episode_already_announced(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> bool:
    """True when this park episode's follow-up is already on the thread.

    Read rather than remembered: a tick whose pinned write failed after
    GitHub accepted the comment leaves no local trace of it, so the thread
    past `last_action_comment_id` is the only record that survives. Scoped to
    the episode by that same watermark -- the id of the mention this park was
    filed with -- so an older follow-up sitting below it cannot silence a
    later park's.
    """
    watermark = state.get(_LAST_ACTION_COMMENT_ID)
    return any(
        _RECOVERY_FOLLOWUP_MARKER in (issue_comment.body or "")
        for issue_comment in gh.comments_after(issue, watermark)
    )


def _recovery_followup_comment(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    park_reason: object,
    outcome: str,
) -> Optional[str]:
    """The follow-up a park that just healed itself owes the issue, or None.

    `last_action_comment_id` is the evidence that a HITL mention was posted:
    `_park_awaiting_human` stamps it at the comment it just left, so a park
    carrying none never pinged anybody and closing a loop nobody was in would
    be pure churn. The text carries no @mention for the same reason -- the
    point is to retire the alarming last word on the thread, not to notify a
    second time.

    Returns None for a reason/outcome pair `_RECOVERY_DETAILS` does not name,
    so a park reason added to `_VALIDATING_TRANSIENT_PARK_REASONS` later
    stays silent until someone writes the sentence that describes it, and None
    again when `_episode_already_announced` finds this episode's follow-up
    already posted. The thread read runs last, so only a tick that has both a
    mention to retire and words for what healed pays for it.
    """
    if state.get(_LAST_ACTION_COMMENT_ID) is None:
        return None
    detail = _RECOVERY_DETAILS.get((park_reason, outcome))
    if detail is None:
        return None
    if _episode_already_announced(gh, issue, state):
        return None
    return (
        f":arrows_counterclockwise: Recovered automatically: {detail}; "
        f"processing resumed. No action needed.\n\n{_RECOVERY_FOLLOWUP_MARKER}"
    )
