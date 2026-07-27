# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The relabel to `in_review`, and the watermark that has to precede it.

Both docs outcomes -- a pushed commit and a confirmed no-change -- leave the
approval, squash, and PR watermarks validating wrote untouched and advance to
`in_review`. What they cannot leave untouched is `pr_last_comment_id`. The
awaiting-human resume advances `last_action_comment_id` past the human reply it
fed into the docs prompt, but in_review scans `comments_after(issue,
pr_last_comment_id)` and only falls back to `last_action_comment_id` when that
field is None. A `pr_last_comment_id` validating seeded BEFORE the reply would
therefore replay it as fresh PR feedback and bounce the issue to `fixing` over
work the dev already did.

The ratchet reuses validating's own seed-walk so a PR-conversation comment
sitting between the old watermark and the consumed-through threshold is not
swallowed: the walk stops at the first unread non-orchestrator comment on
either surface, and the consumed-through bound applies to the issue thread
only. `max` keeps a higher in_review watermark from regressing, and a PR fetch
failure is best-effort -- the handoff still advances, and in_review's own
rescan is debounced and correct on its own.
"""
from __future__ import annotations

from github.Issue import Issue

from orchestrator._workflow_state import log
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.state import WorkflowLabel


def _ratchet_in_review_watermark_for_final_docs(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> None:
    """Ratchet `pr_last_comment_id` past issue-thread comments the docs
    pass already consumed during the final-docs hop.

    During documenting's awaiting-human resume the handler advances
    `last_action_comment_id` past the human reply it fed into the
    `_build_documentation_prompt` resume. The final-docs handoff then
    relabels to `in_review`, which scans `comments_after(issue,
    pr_last_comment_id)` and falls back to `last_action_comment_id`
    only when `pr_last_comment_id is None`. Without this ratchet a
    `pr_last_comment_id` validating seeded BEFORE the human's reply
    keeps the older value, the consumed reply replays as fresh PR
    feedback, and in_review bounces the issue to `fixing` over work
    the dev has already addressed.

    Reuse `_latest_pr_comment_ids` (the same seed-walk validating uses
    at its approval handoff) so a PR-conversation comment with id
    between the prior `pr_last_comment_id` and the consumed-through
    threshold is NOT swallowed -- the walk stops at the first unread
    non-orchestrator comment on either surface. `consumed_through` is
    applied to the issue thread only inside the walk, which is what
    keeps PR-conversation feedback visible to in_review's
    fresh-feedback scan. Ratchets via `max` so a previous in_review
    tick's higher watermark is never regressed.

    A PR fetch failure is treated as best-effort: log and skip, so the
    docs handoff itself still advances. In the worst case in_review
    will route to `fixing` and the rescan there is debounced and
    correct on its own.
    """
    from orchestrator import workflow as _wf

    pr_number = state.get("pr_number")
    if pr_number is None:
        return
    try:
        pr = gh.get_pr(int(pr_number))
    except Exception as error:
        log.warning(
            "issue=#%s could not fetch PR #%s to ratchet "
            "`pr_last_comment_id` on the final-docs handoff: %s",
            issue.number, pr_number, error,
        )
        return

    candidate, _ = _wf._latest_pr_comment_ids(gh, issue, pr, state)
    prev_wm = state.get("pr_last_comment_id")
    if isinstance(prev_wm, int):
        candidate = (
            prev_wm if candidate is None
            else max(candidate, prev_wm)
        )
    if candidate is None:
        return
    state.set("pr_last_comment_id", candidate)


def _advance_after_docs_push(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> None:
    """Route the issue forward after a successful docs push.

    Advance to `in_review` -- the approval comment, squash comment, and
    PR watermarks set by validating remain on state untouched, with the
    in-review issue-comment watermark ratcheted past anything the
    awaiting-human resume already consumed.
    """
    _ratchet_in_review_watermark_for_final_docs(gh, issue, state)
    gh.set_workflow_label(issue, WorkflowLabel.IN_REVIEW)


def _advance_after_docs_no_change(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> None:
    """Route the issue forward after a clean no-change docs verdict.

    No commit landed, so the PR head is unchanged. Ratchet the in-review
    issue-comment watermark past any issue-thread reply the
    awaiting-human resume already consumed, and advance to `in_review`.
    """
    _ratchet_in_review_watermark_for_final_docs(gh, issue, state)
    gh.set_workflow_label(issue, WorkflowLabel.IN_REVIEW)
