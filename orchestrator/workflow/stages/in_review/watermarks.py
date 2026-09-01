# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What this stage has already looked at, on the surfaces it looks at.

Both halves here answer the same question in opposite directions. The ratchet
decides what a route just consumed is allowed to hide: a park writes an issue
comment, so without moving the watermark past it the next tick reads the
orchestrator's own HITL message as fresh human feedback and routes the issue
to `fixing` against it. The seed decides what a first tick is allowed to
forget: an issue that reached `in_review` before the validating handoff seeded
watermarks -- or by a manual relabel -- has none at all, and scanning from
`None` would treat the whole history, pickup greeting included, as fresh
feedback.

Both are deliberately narrow. The ratchet only moves the issue-side watermark,
because the inline-review and review-summary surfaces are consumed by the
`fixing` handler rather than here, and moving them would hide feedback this
stage never read. The seed persists 0 for an empty surface rather than leaving
the key unset, because an unset key would re-run the seed next tick and
swallow the first human review that arrived in between.

`_comment_created_at` sits with them because the debounce that reads it spans
both surfaces: a PullRequestReview stamps `submitted_at` where an IssueComment
stamps `created_at`, and the fakes can leave either unset.
"""
from __future__ import annotations

from datetime import UTC, datetime

from github.Issue import Issue

from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.stages.in_review import models as _models, state as _state


def _comment_created_at(comment) -> datetime | None:
    """Return a tz-aware UTC datetime for a comment, or None if unavailable.

    Real PyGithub `IssueComment.created_at` is always set, but the fakes used
    in tests can leave it None when the test doesn't care about debounce.
    PullRequestReview surfaces its timestamp as `submitted_at` rather than
    `created_at`, so the in_review debounce reads either. Naive datetimes are
    interpreted as UTC (PyGithub returns naive UTC).
    """
    ca = getattr(comment, "created_at", None)
    if ca is None:
        ca = getattr(comment, "submitted_at", None)
    if ca is None:
        return None
    if ca.tzinfo is None:
        return ca.replace(tzinfo=UTC)
    return ca


def _bump_in_review_watermarks(
    ctx: _models._InReviewContext, *, issue_space_new: list | None = None,
) -> None:
    """Push the in_review issue-side watermark (`pr_last_comment_id`) past
    everything seen so far AND past any park comment just written on the issue
    thread.

    Without this, a park-and-write at in_review (unmergeable PR, failed dev fix)
    leaves `pr_last_comment_id` lagging behind the orchestrator park message it
    just posted; the next tick scans the issue thread from the older watermark
    and routes the orchestrator's own HITL ping as fresh PR feedback to
    `fixing`. The ratchet is one-way (only ever increases), so callers pass
    just-consumed comments or omit them and let `latest_comment_id` carry it.

    Only the issue-side watermark moves here. The inline-review and
    review-summary watermarks belong to the `fixing` handler, which advances
    them when it consumes that feedback; in_review never consumes review-surface
    comments itself (it routes them to `fixing`), so there is nothing to ratchet
    past on those surfaces.
    """
    candidates: list[int] = []
    cur_issue_wm = ctx.state.get(_state._PR_LAST_COMMENT_ID)
    if isinstance(cur_issue_wm, int):
        candidates.append(cur_issue_wm)
    last_action = ctx.state.get("last_action_comment_id")
    if isinstance(last_action, int):
        candidates.append(last_action)
    latest = ctx.gh.latest_comment_id(ctx.issue)
    if isinstance(latest, int):
        candidates.append(latest)
    if issue_space_new:
        candidates.extend(comment.id for comment in issue_space_new)
    if candidates:
        ctx.state.set(_state._PR_LAST_COMMENT_ID, max(candidates))


def _seed_missing_watermark(state: PinnedState, key: str, fetch) -> bool:
    """Seed a single missing review-surface watermark past the latest id
    currently visible on that surface, or 0 when it is empty. Returns whether
    a seed was written (so the caller knows a persist is needed).

    `fetch` is a thunk so the surface is only queried when `key` is unset --
    an already-seeded watermark must not trigger a redundant GitHub read.
    Persisting 0 for an empty surface (rather than leaving the key unset) is
    what stops the migration from re-firing next tick and swallowing the
    first human review added in between; see `_seed_legacy_in_review_watermarks`.
    """
    if state.get(key) is not None:
        return False
    surface_comments = list(fetch())
    state.set(
        key,
        max(comment.id for comment in surface_comments)
        if surface_comments
        else 0,
    )
    return True


def _seed_legacy_in_review_watermarks(
    gh: GitHubClient, issue: Issue, pr, state: PinnedState,
) -> None:
    """First-tick migration: seed any missing in_review watermark past every
    comment currently visible on its surface, and record the seed in pinned
    state immediately.

    Issues that reached `in_review` before the validating handoff started
    seeding watermarks (or that were manually relabeled, or whose handoff
    failed to snapshot the PR) sit on `_handle_in_review` with
    `pr_last_comment_id`/`pr_last_review_comment_id`/`pr_last_review_summary_id`
    all unset. Without this seed, the next tick would call
    `comments_after(..., None)` on each surface and treat every historical
    comment -- including the orchestrator's own pickup / PR-opened / approval
    messages -- as fresh PR feedback once the debounce expires, routing the
    issue to `fixing` over its own historical messages.

    Tests that want to drive `_handle_in_review` against pre-existing comments
    seed the relevant watermark explicitly so this helper is a no-op for them.
    """
    # Each missing watermark is persisted on this tick -- 0 if the surface
    # currently has no content, otherwise the latest visible id. Persisting
    # 0 in the empty case is what stops the migration from re-firing on the
    # next tick: if we left the watermark unset, the FIRST human inline /
    # summary review added afterward would be consumed by a re-run of this
    # seed before `_handle_in_review` builds `new_comments`, so the fresh
    # feedback route would silently swallow that first review.
    seeded = False
    if (
        state.get(_state._PR_LAST_COMMENT_ID) is None
        and state.get("last_action_comment_id") is None
    ):
        candidates: list[int] = []
        issue_latest = gh.latest_comment_id(issue)
        if isinstance(issue_latest, int):
            candidates.append(issue_latest)
        pr_conv = list(gh.pr_conversation_comments_after(pr, None))
        if pr_conv:
            candidates.append(max(comment.id for comment in pr_conv))
        state.set(_state._PR_LAST_COMMENT_ID, max(candidates) if candidates else 0)
        seeded = True

    if _seed_missing_watermark(
        state, "pr_last_review_comment_id",
        lambda: gh.pr_inline_comments_after(pr, None),
    ):
        seeded = True
    if _seed_missing_watermark(
        state, "pr_last_review_summary_id",
        lambda: gh.pr_reviews_after(pr, None),
    ):
        seeded = True

    if seeded:
        gh.write_pinned_state(issue, state)
