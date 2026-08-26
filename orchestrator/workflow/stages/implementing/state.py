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

# The park a handoff refuses on: the checkout is not the commit the size
# gate approved. It is its own reason because the recovery is neither a
# session retry nor a re-measurement -- what it asks for is the worktree
# back on that commit, and until then no stage past this one may read it.
_CANDIDATE_MOVED = "late_candidate_moved"

# The commit this issue owes a publication and no push has carried yet. It
# goes down in the same write that APPROVES one -- the retirement a small
# candidate earns, and the exemption a `single` verdict records -- because
# both of those writes drop the record that used to name the commit, and the
# push they license runs after them. Without it a tick that died in that
# window would leave nothing on the issue naming the work: a replacement host
# rebuilds the checkout from the base or the plan pull request, finds a head
# nothing contradicts, and publishes it or pays for a second developer over an
# implementation the first one already finished.
#
# So it is proved before anything spawns and it is what the park that refuses
# an unpublishable checkout is answered by: a worktree put back on that commit
# is the one the reading was taken over, so the recovery republishes it rather
# than asking a human for guidance. Dropped by the handoff that spends it, and
# by the adjudication that supersedes it.
_APPROVED_SHA = "late_approved_sha"

# The commit this stage last PUSHED, written durably ahead of the relabel that
# hands the issue to review. Between those two the branch is on the remote and
# a pull request carries it, while the label still says implementing and every
# record the gate decided by is spent -- so a relabel that failed, or a process
# that died in between, leaves the next tick reading a published branch as work
# nobody has ruled on. Measured again there against a base that has moved or a
# ceiling that was retuned, it can be routed to adjudication with the push and
# the pull request already made, which is the one outcome the size gate exists
# to prevent.
#
# It names one commit and only it, which is the whole invalidation rule: work
# committed on top is work this stage has not published, and is measured as
# the fresh candidate it is. So there is no clearing step -- the next
# publication overwrites it, and a developer's next commit moves the head off
# it.
_PUBLISHED_SHA = "implementing_published_sha"

_PARK_REASON = "park_reason"

_PRE_IMPLEMENT_SHA = "pre_implement_sha"

# The tip a read-only stage's relabel certified as "what the branch already
# carried". The recovered-worktree shortcut reads commits ahead of base as a
# previous dev run's, which an issue arriving from `discussion` on its PR's
# branch would trip on its first tick -- the dev would be skipped and the
# inherited commits republished as its work. Written by
# `read_only_relabel._clear_stale_read_only_park` from the round anchor it
# retires; spent by `spawn._prepare_active_dev_run`.
_READ_ONLY_BASELINE_SHA = "read_only_baseline_sha"

# The head an accepted plan handoff is moving the branch onto, written before
# the move and retired by the write that records where it landed. Without it,
# the tick after a crash in between cannot tell the branch that move left --
# sitting on the plan PR's live head -- from a developer's own commit, and the
# recovered-worktree shortcut would push the reviewers' amendment as the
# implementation with no agent having run. Written and spent by
# `read_only_relabel._readvance_plan_handoff`.
_HANDOFF_ANCHOR_SHA = "read_only_anchor_sha"

_BRANCH = "branch"

_PR_NUMBER = "pr_number"

_IMPLEMENTING_STAGE = "implementing"

_REASON_STUCK = "stuck"

_PR_BODY_AGENT_MESSAGE_CAP = 60000

_PR_BODY_TRUNCATION_MARKER = "_…(message truncated)_"
