# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The pinned-state fields this stage reads and writes, and how it names children.

Every owner in the package keys the same durable fields, so they are spelled
once here: a typo in a key is a silently-lost park or a parent that forgets its
children, and neither surfaces until an issue is already stuck. `_issue_ref_list`
sits with them because it is the one rendering of those recorded numbers -- the
held-dependency log line, the rejected- and closed-child parks, and the drift
notice all quote children the same way.
"""
from __future__ import annotations

_AWAITING_HUMAN = "awaiting_human"

_LAST_ACTION_COMMENT_ID = "last_action_comment_id"

_CHILDREN = "children"

_UMBRELLA = "umbrella"

_PARK_REASON = "park_reason"

_PARENT_NUMBER = "parent_number"

_CREATED_AT = "created_at"

_DONE = "done"

_HeldChild = tuple[int, list[int]]


def _issue_ref_list(numbers: list) -> str:
    """Render issue/child numbers as a `#a, #b` comma-joined reference list."""
    return ", ".join(f"#{number}" for number in numbers)
