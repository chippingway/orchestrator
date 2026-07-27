# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The pinned-state keys and CLI markers the implementing owners share.

Every field name here is a key in the JSON comment live issues already carry,
so these are wire strings, not internal spellings: renaming one is a migration
of every open issue, not a refactor. They sit in one module because the owners
that write them and the owners that read them are different files -- the park
that sets `park_reason` is not the preflight that clears it, and the timeout
that persists `pre_implement_sha` is not the recovery that publishes off it.

The marker tuples are the other half: each is a set of CLI phrasings one
classifier in `session_read` matches a failed run against, and each is grouped
by the recovery it selects (drop the session, wait for a quota reset, park a
question) rather than by the backend that emits it.
"""
from __future__ import annotations

from typing import Tuple

_SILENT_PARKS_BEFORE_FRESH_SESSION = 2

_CLAUDE_STALE_SESSION_STDERR_MARKERS: Tuple[str, ...] = (
    "no conversation found with session id",
    "no conversation found with id",
    "no conversation with session id",
    "conversation not found",
)

_CLAUDE_CONTEXT_OVERFLOW_MARKERS: Tuple[str, ...] = (
    "prompt is too long",
    "input is too long",
    "input length and `max_tokens` exceed context limit",
)

_CLAUDE_SESSION_LIMIT_MESSAGE_MARKERS: Tuple[str, ...] = (
    "you've hit your session limit",
    "you've hit your usage limit",
    "you've reached your session limit",
    "you've reached your usage limit",
    "claude usage limit reached",
    "claude ai usage limit reached",
)

_DEV_AGENT = "dev_agent"

_DEV_SESSION_ID = "dev_session_id"

_CODEX_SESSION_ID = "codex_session_id"

_SILENT_PARK_COUNT = "silent_park_count"

_DEV_RESUME_COUNT = "dev_resume_count"

_RETRY_WINDOW_START = "retry_window_start"

_RETRY_COUNT = "retry_count"

_AWAITING_HUMAN = "awaiting_human"

_LAST_ACTION_COMMENT_ID = "last_action_comment_id"

_AGENT_TIMEOUT = "agent_timeout"

_PARK_REASON = "park_reason"

_PRE_IMPLEMENT_SHA = "pre_implement_sha"

_BRANCH = "branch"

_IMPLEMENTING_STAGE = "implementing"

_REASON_STUCK = "stuck"

_PR_BODY_AGENT_MESSAGE_CAP = 60000

_PR_BODY_TRUNCATION_MARKER = "_…(message truncated)_"
