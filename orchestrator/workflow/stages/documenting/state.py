# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The pinned-state keys the documenting owners share.

Every name here is a key in the JSON comment live issues already carry, so
these are wire strings rather than internal spellings: renaming one is a
migration of every open issue, not a refactor. They sit in one module because
the owner that writes a key is rarely the owner that reads it -- the park that
stamps `park_reason` is not the precondition that classifies a continue
against it, and the resume that advances `last_action_comment_id` is not the
drift block that reads it back to decide whether a retry signal arrived.
"""
from __future__ import annotations

_PARK_REASON = "park_reason"

_AWAITING_HUMAN = "awaiting_human"

_LAST_ACTION_COMMENT_ID = "last_action_comment_id"
