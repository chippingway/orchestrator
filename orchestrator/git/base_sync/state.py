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

from orchestrator.workflow.state import WorkflowLabel

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

# The head the replay left, recorded once git has produced it and before the
# gate is entered. The anchor beside it says which head the push is leased
# against and brings an interrupted attempt back; this says which local commit
# that attempt made, which is the one thing the anchor cannot prove. A rebase
# REPLAYS the branch, so the checkout diverges from the head the pull request
# carries -- and a recovery that read the divergence alone as its own work
# would force-push whatever the checkout had become over the candidate on the
# remote, under a lease the anchor satisfies.
_PENDING_REWRITE_SHA = "pending_auto_base_rebase_rewrite_sha"

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
