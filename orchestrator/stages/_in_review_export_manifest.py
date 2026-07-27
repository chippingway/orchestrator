# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Immutable lazy-export inventory for :mod:`orchestrator.stages.in_review`."""

from __future__ import annotations

from orchestrator._compat_exports import export_group

EXPORTS = (
    *export_group(
        "dataclasses",
        (("dataclass", "dataclass"),),
    ),
    *export_group(
        "datetime",
        (
            ("datetime", "datetime"),
            ("timezone", "timezone"),
        ),
    ),
    *export_group(
        "github.Issue",
        (("Issue", "Issue"),),
    ),
    *export_group(
        "orchestrator._workflow_dependencies",
        (("config", "config"),),
    ),
    *export_group(
        "orchestrator.github.client",
        (("GitHubClient", "GitHubClient"),),
    ),
    *export_group(
        "orchestrator.github.comments",
        (("filter_trusted", "filter_trusted"),),
    ),
    *export_group(
        "orchestrator.github.pinned_state",
        (("PinnedState", "PinnedState"),),
    ),
    *export_group(
        "orchestrator.workflow.stages.in_review.drift",
        (
            ("_build_drift_resume_prompt", "_build_drift_resume_prompt"),
            ("_dispose_drift_result", "_dispose_drift_result"),
            ("_drift_unread_pr_conv", "_drift_unread_pr_conv"),
            ("_drift_worktree", "_drift_worktree"),
            ("_handle_user_content_drift", "_handle_user_content_drift"),
            ("_resume_dev_for_drift", "_resume_dev_for_drift"),
        ),
    ),
    *export_group(
        "orchestrator.workflow.stages.in_review.feedback",
        (
            ("_consume_fresh_feedback", "_consume_fresh_feedback"),
            ("_drop_orchestrator_comments", "_drop_orchestrator_comments"),
            ("_fresh_issue_space", "_fresh_issue_space"),
            ("_issue_side_watermark", "_issue_side_watermark"),
            ("_scan_fresh_pr_feedback", "_scan_fresh_pr_feedback"),
            ("_stay_parked", "_stay_parked"),
        ),
    ),
    *export_group(
        "orchestrator.workflow.stages.in_review.fixing_route",
        (
            ("_record_pending_fix_bookmarks", "_record_pending_fix_bookmarks"),
            ("_route_feedback_to_fixing", "_route_feedback_to_fixing"),
        ),
    ),
    *export_group(
        "orchestrator.workflow.stages.in_review.handler",
        (
            ("_handle_in_review", "_handle_in_review"),
            ("_park_missing_pr_number", "_park_missing_pr_number"),
        ),
    ),
    *export_group(
        "orchestrator.workflow.stages.in_review.merge_gate",
        (
            (
                "_final_docs_handoff_completed_for_head",
                "_final_docs_handoff_completed_for_head",
            ),
            ("_handle_mergeable_gate", "_handle_mergeable_gate"),
            ("_head_is_approved", "_head_is_approved"),
        ),
    ),
    *export_group(
        "orchestrator.workflow.stages.in_review.models",
        (
            ("_DriftResume", "_DriftResume"),
            ("_InReviewContext", "_InReviewContext"),
        ),
    ),
    *export_group(
        "orchestrator.workflow.stages.in_review.state",
        (("_PR_LAST_COMMENT_ID", "_PR_LAST_COMMENT_ID"),),
    ),
    *export_group(
        "orchestrator.workflow.stages.in_review.watermarks",
        (
            ("_bump_in_review_watermarks", "_bump_in_review_watermarks"),
            ("_comment_created_at", "_comment_created_at"),
            ("_seed_legacy_in_review_watermarks", "_seed_legacy_in_review_watermarks"),
            ("_seed_missing_watermark", "_seed_missing_watermark"),
        ),
    ),
    *export_group(
        "orchestrator.workflow.state",
        (("WorkflowLabel", "WorkflowLabel"),),
    ),
    *export_group(
        "typing",
        (
            ("Any", "Any"),
            ("Optional", "Optional"),
        ),
    ),
)
EXPORTED_NAMES = None
