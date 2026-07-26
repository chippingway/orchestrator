# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Pinned-state keys, park reasons, and detour labels for one rebase attempt.

These values are a public contract in two directions: the string keys and park
reasons are already written into pinned-state comments on live issues, and the
logger name is what operator log filters select on. Both are spelled out
literally here rather than derived from the module path so that moving this
owner cannot rename either one.
"""
from __future__ import annotations

import logging

from orchestrator.state_machine import WorkflowLabel

log = logging.getLogger('orchestrator.base_sync')

_PR_REFRESH_DETOUR_LABELS = frozenset(
    (
        WorkflowLabel.VALIDATING, WorkflowLabel.DOCUMENTING,
        WorkflowLabel.IN_REVIEW, WorkflowLabel.FIXING,
    ),
)

_PARK_REASON = "park_reason"

_AWAITING_HUMAN = "awaiting_human"

_REVIEW_ROUND = "review_round"

_CONFLICT_ROUND = "conflict_round"

_PENDING_PUSH_SHA = "pending_auto_base_rebase_push_sha"

_REASON_AUTO_BASE_REBASE_FAILED = "auto_base_rebase_failed"

_REASON_AUTO_BASE_REBASE_PUSH_FAILED = "auto_base_rebase_push_failed"

_ERROR_SNIPPET_LEN = 120

_AUTO_REBASE_PARK_REASONS = frozenset(
    (
        _REASON_AUTO_BASE_REBASE_FAILED,
        "auto_base_rebase_dirty",
        _REASON_AUTO_BASE_REBASE_PUSH_FAILED,
    ),
)
