# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The batch that started the loop, rebuilt from ids after the watermarks moved.

The `pending_fix_*` ids the in_review route records are deliberately not
watermarks. The first dev resume advances the in_review watermarks past the
feedback that triggered the route, so from that moment on the triggering batch
cannot be recovered by rescanning anything -- and a `/orchestrator continue` on
a poisoned session needs exactly that batch, or the retry re-grounds a fresh
session on the command text alone and the review feedback is lost.

So the reconstruction re-fetches each surface unbounded and keeps only the
recorded ids. Filtering by id inherently drops the orchestrator's own comments
(their ids were never in the batch) and survives any watermark advance; an item
deleted on GitHub since simply falls out.

The validating route records no id lists at all -- its single replay anchor is
the reviewer-feedback PR comment, which the orchestrator authored itself, so it
is fetched separately here and the caller adds it OUTSIDE the trust filter.

The clear is the other half of the same contract: bookmarks that outlive their
round would mis-flag the next one, so a pushed fix, a returned ACK, and a
silent validating recovery all drop them.
"""
from __future__ import annotations

from orchestrator.workflow.stages.fixing import state as _state


# Every bookmark one fix route leaves, and the value clearing it writes.
# Spelled as pairs rather than as a sequence of writes, so a caller that has
# to hand the clear somewhere else -- the size gate, which applies a route's
# bookkeeping inside its own durable write -- describes it in the same terms
# this owner does. The last is the validating-route reviewer-feedback replay
# anchor (recorded by `_handle_validating_changes_requested`), cleared
# alongside the in_review-route bookmarks so a later route writes fresh values
# and a session-failure park never replays an already-addressed reviewer round.
_CLEARED_BOOKMARKS = (
    (_state._PENDING_FIX_AT, None),
    ("pending_fix_issue_max_id", None),
    ("pending_fix_review_max_id", None),
    ("pending_fix_review_summary_max_id", None),
    ("pending_fix_issue_ids", None),
    ("pending_fix_review_ids", None),
    ("pending_fix_review_summary_ids", None),
    ("pending_fix_reviewer_comment_id", None),
)


def _cleared_pending_fix_bookmarks() -> tuple:
    """The pinned fields a cleared fix route leaves, as key/value pairs."""
    return _CLEARED_BOOKMARKS


def _clear_pending_fix_bookmarks(state) -> None:
    for key, cleared in _CLEARED_BOOKMARKS:
        state.set(key, cleared)


def _pending_fix_id_set(state, ids_key: str, max_id_key: str) -> set:
    """Resolve the persisted batch ids for one feedback surface.

    Prefers the full `pending_fix_*_ids` list the in_review route records.
    Falls back -- conservatively -- to the single `pending_fix_*_max_id`
    for issues parked before the id lists existed: the max id is the only
    member a legacy bookmark can vouch for, so the reconstruction includes
    just that one item rather than guessing a lower bound the advanced
    watermark can no longer supply. `bool` is rejected explicitly because
    it is an `int` subclass and a stray `True` must not read as id 1.
    """
    ids = state.get(ids_key)
    if isinstance(ids, list) and ids:
        return {int(comment_id) for comment_id in ids}
    max_id = state.get(max_id_key)
    if isinstance(max_id, int) and not isinstance(max_id, bool):
        return {max_id}
    return set()


def _reviewer_anchor_comment(gh, pr, state):
    """Fetch the validating-route reviewer-feedback replay anchor, or None.

    `_handle_validating_changes_requested` posts the automated reviewer's
    CHANGES_REQUESTED feedback as one PR-conversation comment and records its
    id in `pending_fix_reviewer_comment_id` (WITHOUT setting `pending_fix_at`,
    which discriminates the two routes' review-round accounting). That route
    preserves no `pending_fix_*_ids`, so this single comment is the only
    replayable input for a `/orchestrator continue` on a session-failure park
    that came through validating.

    Re-fetch it by id from the PR conversation surface. The comment is
    orchestrator-authored -- normally dropped from a rescan by the id-set
    filter and by `filter_trusted` when the PAT login is not allowlisted --
    but it carries the reviewer's own trusted feedback, so the caller adds it
    OUTSIDE the trust filter. `bool` is rejected explicitly (it is an `int`
    subclass and a stray `True` must not read as id 1). Returns None when the
    anchor id is unset / not an int, or the comment can no longer be fetched
    (deleted, or a PR read that returned without it) -- the empty-batch
    refusal then holds.
    """
    anchor_id = state.get("pending_fix_reviewer_comment_id")
    if not isinstance(anchor_id, int) or isinstance(anchor_id, bool):
        return None
    for pr_comment in gh.pr_conversation_comments_after(pr, None):
        if pr_comment.id == anchor_id:
            return pr_comment
    return None


def _reconstruct_issue_space(gh, issue, pr, state) -> list:
    """Batch items from the shared issue-thread + PR-conversation id space.

    Re-fetches both surfaces in full (`after_id=None`) and keeps only the ids
    recorded at route time, sorted by id -- so the reconstruction survives the
    watermark advancement that follows the first dev resume.
    """
    issue_ids = _pending_fix_id_set(
        state, "pending_fix_issue_ids", "pending_fix_issue_max_id",
    )
    if not issue_ids:
        return []
    matched = [
        issue_comment
        for issue_comment in gh.comments_after(issue, None)
        if issue_comment.id in issue_ids
    ]
    matched += [
        pr_comment
        for pr_comment in gh.pr_conversation_comments_after(pr, None)
        if pr_comment.id in issue_ids
    ]
    matched.sort(key=lambda comment: comment.id)
    return matched


def _reconstruct_review_comments(gh, pr, state) -> list:
    """Inline review-comment batch items recorded at route time, sorted by id."""
    review_ids = _pending_fix_id_set(
        state, "pending_fix_review_ids", "pending_fix_review_max_id",
    )
    if not review_ids:
        return []
    matched = [
        review_comment
        for review_comment in gh.pr_inline_comments_after(pr, None)
        if review_comment.id in review_ids
    ]
    matched.sort(key=lambda comment: comment.id)
    return matched


def _reconstruct_review_summaries(gh, pr, state) -> list:
    """Review-summary batch items recorded at route time, sorted by id."""
    summary_ids = _pending_fix_id_set(
        state,
        "pending_fix_review_summary_ids",
        "pending_fix_review_summary_max_id",
    )
    if not summary_ids:
        return []
    matched = [
        review
        for review in gh.pr_reviews_after(pr, None)
        if review.id in summary_ids
    ]
    matched.sort(key=lambda review: review.id)
    return matched
