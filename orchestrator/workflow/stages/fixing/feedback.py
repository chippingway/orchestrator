# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The three watermarks this stage scans forward from and ratchets back to.

The rescan reads the in_review watermarks, never the `pending_fix_*`
bookmarks: the bookmarks are the replay source a `/orchestrator continue`
needs, and consuming them here would spend them on the ordinary tick.

The advance is deliberately the narrower half of that pair. Each surface moves
only to the max id actually fed to the dev on that surface, ratcheted against
what is already there -- the broader `_bump_in_review_watermarks` also pulls in
`gh.latest_comment_id(issue)`, which can leap past a human comment that landed
after the scan and was never quoted in the prompt. Swallowing it would drop
real feedback on the pushed path (the next in_review tick misses it) and on the
park path (the next fixing tick's stay-parked gate drops it), which is why the
advance runs on BOTH outcomes rather than only on success.

Orchestrator comments are stripped by recorded id AND by the hidden body
marker, because the id ledger is capped and evicts on long-lived issues while
the marker stays on the comment forever. The trusted-author filter sits above
every surface, so an outsider on a public PR can neither resume the dev nor
extend the quiet window; an empty allowlist trusts everyone.
"""
from __future__ import annotations

from github.Issue import Issue

from orchestrator.github.client import GitHubClient
from orchestrator.github.comments import filter_trusted
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.stages.fixing import models as _models


def _new_issue_space_feedback(gh: GitHubClient, issue: Issue, pr, state) -> list:
    """Unread issue-thread + PR-conversation comments past the in_review
    watermark, sorted by id, with orchestrator comments and untrusted authors
    dropped.

    The two surfaces share the IssueComment id namespace, so one watermark
    covers both. Mirror `_handle_in_review`'s fallback: if no PR-side
    watermark exists yet (an in_review tick that routed to `fixing` before
    ever seeding `pr_last_comment_id` -- e.g. a manual relabel into
    `in_review` without going through validating, or a legacy issue that
    pre-dates the watermark migration), fall back to `last_action_comment_id`.
    Without this, `comments_after` / `pr_conversation_comments_after` would be
    called with `after_id=None` and re-feed every historical comment into the
    dev's `_build_pr_comment_followup` prompt as fresh feedback.

    Orchestrator comments are filtered by id AND the hidden body marker -- the
    id cap evicts old ids on long-lived issues, after which an id-only filter
    would start re-feeding old bot comments to the dev. Untrusted authors are
    dropped last (see `filter_trusted`) so an outsider's comment never resumes
    the dev or extends the debounce window; an empty allowlist trusts everyone.
    """
    issue_wm = state.get("pr_last_comment_id")
    if issue_wm is None:
        issue_wm = state.get("last_action_comment_id")
    orchestrator_ids = _comments._orchestrator_ids(state)
    unread = [
        comment
        for comment in list(gh.comments_after(issue, issue_wm))
        + list(gh.pr_conversation_comments_after(pr, issue_wm))
        if comment.id not in orchestrator_ids
        and _comments._ORCH_COMMENT_MARKER not in (comment.body or "")
    ]
    return filter_trusted(sorted(unread, key=lambda comment: comment.id))


def _new_review_comment_feedback(gh: GitHubClient, pr, state) -> list:
    """Unread inline review comments past `pr_last_review_comment_id`, sorted
    by id and trust-filtered.

    Inline review comments live in their own id space the orchestrator never
    posts on, so no orchestrator filter is needed -- only the trust gate.
    """
    review_wm = state.get("pr_last_review_comment_id")
    return filter_trusted(sorted(
        gh.pr_inline_comments_after(pr, review_wm),
        key=lambda comment: comment.id,
    ))


def _new_review_summary_feedback(gh: GitHubClient, pr, state) -> list:
    """Unread review summaries past `pr_last_review_summary_id`, sorted by id
    and trust-filtered (same rationale as `_new_review_comment_feedback`).
    """
    review_summary_wm = state.get("pr_last_review_summary_id")
    return filter_trusted(sorted(
        gh.pr_reviews_after(pr, review_summary_wm),
        key=lambda review: review.id,
    ))


def _rescan_fixing_feedback(
    gh: GitHubClient, issue: Issue, pr, state,
) -> _models._FixingFeedback:
    """Rescan the four PR-feedback surfaces for comments past the in_review
    watermarks (NOT the `pending_fix_*` bookmarks -- those stay in pinned
    state as the reconstruction source for `_reconstruct_pending_fix_batch`).

    Returns the three per-surface batches plus `all_items`, concatenated in
    prompt order: issue-space (issue-thread + PR-conversation), then inline
    review comments, then review summaries.
    """
    issue_space = _new_issue_space_feedback(gh, issue, pr, state)
    review_comments = _new_review_comment_feedback(gh, pr, state)
    review_summaries = _new_review_summary_feedback(gh, pr, state)
    return _models._FixingFeedback(
        issue_space=issue_space,
        review_comments=review_comments,
        review_summaries=review_summaries,
        all_items=issue_space + review_comments + review_summaries,
    )


def _advance_consumed_watermarks(
    state, feedback: _models._FixingFeedback,
) -> None:
    """Advance the three in_review watermarks ONLY to the max id consumed
    per surface, ratcheted against the existing watermark.

    Called once on every dev-result outcome (BOTH the pushed-fix path
    AND the park/failure path) before the pushed/non-pushed split, so
    a concurrent human comment that landed between `feedback` and
    this call survives to the next tick on either branch. The broader
    `_bump_in_review_watermarks` is deliberately NOT used here: it
    also pulls in `gh.latest_comment_id(issue)`, which could leap the
    watermark past a concurrent issue-thread comment the dev never saw
    in its prompt -- silently swallowing real feedback on the pushed
    path (the next in_review tick would miss it) and on the
    park/failure path (the next fixing tick's
    `awaiting_human and not new_feedback` gate would drop it).
    """
    cur_issue_wm = state.get("pr_last_comment_id")
    if feedback.issue_space:
        new_wm = max(comment.id for comment in feedback.issue_space)
        if isinstance(cur_issue_wm, int):
            new_wm = max(new_wm, cur_issue_wm)
        state.set("pr_last_comment_id", new_wm)

    cur_review_wm = state.get("pr_last_review_comment_id")
    if feedback.review_comments:
        new_wm = max(comment.id for comment in feedback.review_comments)
        if isinstance(cur_review_wm, int):
            new_wm = max(new_wm, cur_review_wm)
        state.set("pr_last_review_comment_id", new_wm)

    cur_summary_wm = state.get("pr_last_review_summary_id")
    if feedback.review_summaries:
        new_wm = max(review.id for review in feedback.review_summaries)
        if isinstance(cur_summary_wm, int):
            new_wm = max(new_wm, cur_summary_wm)
        state.set("pr_last_review_summary_id", new_wm)
