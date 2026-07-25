# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable PyGithub client surface for workflow and operator code.

Client composition lives in one mixin leaf outside the package, layered over
the check, review, label, issue, pinned-state, and pull-request owners here.
The label, event, and issue owners reach no further than ``state_machine``,
``_static_alias``, ``config``, each other, and the PyGithub types, so their
re-exports bind eagerly here. ``GitHubClient`` resolves lazily through the
module ``__getattr__``: it pulls the full mixin chain, whose leaves import this
package back for the label, review, and pinned-state surfaces, so binding it
eagerly would let a leaf-first import re-enter a half-built initializer. The
pinned-state, review, and check re-exports resolve the same way, keeping the
durable-state owner -- which the review owner reads the pinned marker from and
the check owner inherits through the pull-request one -- off this initializer's
import path.
"""
from __future__ import annotations

from typing import Any

from orchestrator.github import events as _events
from orchestrator.github import issues as _issues
from orchestrator.github import labels as _labels

WORKFLOW_LABEL_SPECS = _labels.WORKFLOW_LABEL_SPECS
WORKFLOW_LABELS = _labels.WORKFLOW_LABELS
BACKLOG_LABEL = _labels.BACKLOG_LABEL
PAUSED_LABEL = _labels.PAUSED_LABEL
COMMUNITY_CONTRIBUTION_LABEL = _labels.COMMUNITY_CONTRIBUTION_LABEL
CONTROL_LABEL_SPECS = _labels.CONTROL_LABEL_SPECS
HARD_SKIP_CONTROL_LABELS = _labels.HARD_SKIP_CONTROL_LABELS
issue_has_label = _labels.issue_has_label
hard_skip_control_label = _labels.hard_skip_control_label
_iter_new_non_pr_issues = _issues.iter_new_non_pr_issues
_issue_query_options = _issues.issue_query_options
_append_event_line = _events.append_event_line
_write_event_record = _events.write_event_record
build_event_record = _events.build_event_record

_HTTP_FORBIDDEN = 403
_HTTP_NOT_FOUND = 404
_ISSUE_STATE_OPEN = "open"
_RECORDED_EVENTS_CAP = 500

# Facade name -> attribute on the pinned-state owner. Resolved lazily so the
# durable-state owner is imported on first use rather than by this initializer.
_PINNED_STATE_EXPORTS = (
    ("PINNED_STATE_MARKER", "PINNED_STATE_MARKER"),
    ("PINNED_STATE_RE", "PINNED_STATE_RE"),
    ("PINNED_STATE_BODY_RE", "PINNED_STATE_BODY_RE"),
    ("PINNED_STATE_TEMPLATE", "PINNED_STATE_TEMPLATE"),
    ("PinnedState", "PinnedState"),
    ("_pinned_state_from_comment", "pinned_state_from_comment"),
)

# Facade name -> attribute on the review owner, resolved lazily for the same
# reason: the review owner reads the pinned-state marker, so an eager binding
# would drag the durable-state owner onto this initializer's import path.
_REVIEW_EXPORTS = (
    ("_REVIEW_CHANGES_REQUESTED", "REVIEW_CHANGES_REQUESTED"),
    ("_review_state_for_head", "review_state_for_head"),
    ("_latest_review_states_for_head", "latest_review_states_for_head"),
    ("_record_latest_review", "record_latest_review"),
    ("_is_actionable_review_summary", "is_actionable_review_summary"),
)

# Facade name -> attribute on the check owner, deferred because that owner
# inherits the pull-request mixin and so reaches the durable-state owner.
_CHECK_EXPORTS = (
    ("_CheckSurfaceRead", "CheckSurfaceRead"),
    ("_normalize_combined_status", "normalize_combined_status"),
    ("_normalize_check_runs", "normalize_check_runs"),
    ("_fold_check_states", "fold_check_states"),
    ("_FAILED_CHECK_RUN_CONCLUSIONS", "FAILED_CHECK_RUN_CONCLUSIONS"),
    ("_SUCCESSFUL_CHECK_RUN_CONCLUSIONS", "SUCCESSFUL_CHECK_RUN_CONCLUSIONS"),
    ("_CHECK_STATE_FAILURE", "CHECK_STATE_FAILURE"),
    ("_CHECK_STATE_PENDING", "CHECK_STATE_PENDING"),
)


def __getattr__(name: str) -> Any:
    """Resolve GitHubClient and the deferred owner re-exports lazily."""
    if name == "GitHubClient":
        from orchestrator.github import client
        return client.GitHubClient
    for owner_name, owner_attr in _PINNED_STATE_EXPORTS:
        if name == owner_name:
            from orchestrator.github import pinned_state
            return getattr(pinned_state, owner_attr)
    for owner_name, owner_attr in _REVIEW_EXPORTS:
        if name == owner_name:
            from orchestrator.github import reviews
            return getattr(reviews, owner_attr)
    for owner_name, owner_attr in _CHECK_EXPORTS:
        if name == owner_name:
            from orchestrator.github import checks
            return getattr(checks, owner_attr)
    raise AttributeError(name)
