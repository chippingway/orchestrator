# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one write every ending of this stage reaches the issue through.

A discussion tick has exactly one kind of ending -- awaiting a human -- so what
differs between the endings is only what the comment says and which reason it
is recorded under. That reason is load-bearing beyond the message: the handler
reads its `discussion_` prefix back on the next tick to decide whose turn it
is, so a park that skipped this funnel would read as a park some other stage
wrote and earn a second round over the top of the first. Stamping it here
rather than at each ending is what makes that structural instead of a rule the
three park owners beside this module have to remember.

The funnel exists because the shared park helper clears `park_reason`: the
stage-specific reason has to be restored after it and persisted, which is also
where the round's staged records finally land.
"""
from __future__ import annotations

from orchestrator.workflow.engine import guards as _guards
from orchestrator.workflow.stages.discussion import models as _models, state as _state


def _park_discussion(
    run: _models._DiscussionRun, message: str, *, reason: str,
) -> None:
    """Park the issue awaiting human under the discussion-stage reason.

    The shared park helper clears `park_reason`, so this funnel restores the
    stage-specific one and persists the completed state mutation -- the single
    durable write every route in this stage reaches the issue through.

    It also stamps `last_action_comment_id` at the newest comment on the
    thread, which this funnel restores for the same kind of reason. That stamp
    is right for a stage whose park ENDS the exchange, but a discussion's park
    is an invitation to answer it, and minutes of agent run separate the thread
    the round read from the thread as it stands now. Anything posted in that
    window -- a human's second thought, an outsider's comment the allowlist may
    later admit -- would be recorded as read by a round that never saw it, and
    nothing here reads a comment twice. What the round did read it has already
    staged, so restoring the value this call was entered with is exactly the
    ceiling to keep. The comment just posted needs no watermark to be skipped:
    `_new_trusted_replies` knows the stage's own messages by id and marker.
    """
    consumed_through = run.state.get(_state._LAST_ACTION_COMMENT_ID)
    _guards._park_awaiting_human(
        run.gh, run.issue, run.state, message, reason=reason,
    )
    run.state.set(_state._PARK_REASON, reason)
    run.state.set(_state._LAST_ACTION_COMMENT_ID, consumed_through)
    # A park IS the report a round owes, so it is what ends the window the
    # open flag marks. Cleared here rather than at each ending, because every
    # one of them lands on this funnel and a flag left standing would have the
    # next tick attribute somebody else's commit to a round already answered.
    run.state.set(_state._ROUND_OPEN, None)
    run.gh.write_pinned_state(run.issue, run.state)
