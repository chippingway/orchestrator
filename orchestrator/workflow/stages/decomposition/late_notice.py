# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The sentence a park owes the issue, until it has actually been said.

A park is two things that cannot be made one operation: a durable claim that
the issue is waiting on a human, and a comment telling them what they are
waiting to do. The claim goes first everywhere in this mode -- a comment
GitHub refuses must not take a finished run's result down with it -- and that
order leaves exactly one gap: a park written and then never announced.

Nothing else closes that gap, because nothing else can tell the difference.
Every late park is reconciled per tick against what pinned state says, and
what pinned state says about a park whose comment failed is identical to what
it says about one whose comment landed. So the next tick reads the flag, takes
the human as told, and says nothing -- on that tick and on every tick after
it. For the parks a fresh attempt supersedes that costs one round of silence
and no more: the attempt re-takes the park and announces the reason it fails
for THEN. For the ones no attempt supersedes -- a categorized question, an
edit nobody has explained, a checkout the developer left dirty -- it is
unbounded, because those parks ARE what the issue is waiting on and their
sentence is the only thing that would ever say so.

So the sentence is written down beside the flag and dropped only once it is
on the thread. This owner is that field: what is owed, which park it explains,
and the one rule about its size. It is deliberately NOT part of the
generation's own key set -- a park outlives the generation that took it, and
the human it named is owed their sentence either way.

The reason travels with the message because the field is issue-wide and the
park it explains may be replaced. A notice matched against a reason the issue
is no longer parked for describes a state that is over, so it is dropped
rather than said.

Size is the one refusal. The pinned comment is shared and bounded, and a
notice quoting an agent's whole reply can be big enough to matter, so what a
write would produce is measured before it is made -- exactly as a recorded
outcome is. A notice past the budget is refused whole rather than shortened:
what that costs is a retry nobody will take, which is worth a loud log line
and is not worth a pinned write that fails and takes the park itself with it.

And the field is a claim about the thread, so the thread is what settles a
disagreement with it. The comment and the write that records it cannot be
made one operation, so the write can fail after the post has landed -- and
what that leaves is a record saying a sentence is owed to a thread that
already has it. Read as owed, it would repeat one comment, which is the same
window every park in this repository has; read as evidence that nobody was
told, it would silence the follow-up a park that heals owes the thread, which
is a promise nothing else keeps. So a notice is looked for on the issue before
it is acted on, and one found there is discharged from what GitHub holds
rather than from what the pinned comment claims -- and only where the thread
shows this orchestrator wrote it, since a sentence anybody can paste back is
one anybody could otherwise use to mark a park explained that nobody ever
explained.
"""
from __future__ import annotations

import logging

from orchestrator.github.comments import authored_by_us
from orchestrator.workflow.stages.decomposition import (
    late_session as _late_session,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    _LateContext,
    _StagedPark,
)

log = logging.getLogger("orchestrator.workflow")

# The notice a park recorded here has still to say out loud. Spelled with the
# mode's own prefix because it is this mode's obligation: another stage's park
# is not one this owner may speak for.
PARK_NOTICE = "late_park_notice"

# The shared park flag this field is the missing half of. Spelled here rather
# than imported for the reason its neighbours spell it: reaching back into the
# owner that stages parks would make this leaf part of the cycle it sits
# under.
_PARK_REASON = "park_reason"

# The consumed-comment watermark a park's own mention ratchets, and only ever
# on a write that landed. That is what makes it the right window to look for
# an undelivered notice in: a sentence whose write failed fell ABOVE the mark
# its post should have moved, while one from an episode that completed sits at
# or below it and cannot answer for a later park carrying the same words.
_LAST_ACTION_COMMENT_ID = "last_action_comment_id"

_REASON = "reason"

_MESSAGE = "message"


def _owed_notice(context: _LateContext) -> _StagedPark | None:
    """The sentence this issue's standing park has still to say, if any.

    Read back as the same staged park the release takes, so a notice owed by
    an earlier tick and one staged by this tick are the same thing to
    everything downstream.

    Matched against the reason the issue is actually parked for. A notice left
    behind by a park something has since replaced or answered explains a state
    the issue is no longer in, and saying it would tell a human to settle a
    thing that is already settled.
    """
    owed = context.state.get(PARK_NOTICE)
    if not isinstance(owed, dict):
        return None
    reason = owed.get(_REASON)
    if not reason or reason != context.state.get(_PARK_REASON):
        return None
    message = owed.get(_MESSAGE)
    if not isinstance(message, str) or not message:
        return None
    return _StagedPark(message=message, reason=reason)


def _owe_notice(context: _LateContext, staged: _StagedPark) -> None:
    """Record this park's sentence as one that has still to be said.

    Staged into memory only, like every other field this mode writes: what
    makes it durable is the write the park itself rides out on, which is what
    keeps the obligation and the park it explains in one write rather than
    two.

    A notice the pinned comment cannot hold is refused, and so is whatever it
    replaces -- the park that owed the older sentence is gone, so keeping it
    would announce the wrong one. What is lost is the retry, not the park and
    not this tick's own attempt to post.
    """
    owed = {_REASON: staged.reason, _MESSAGE: staged.message}
    if not _fits_beside_the_state(context, owed):
        log.error(
            "issue=#%d the notice for park %s does not fit the pinned "
            "comment; it will be posted once and never retried",
            context.issue.number, staged.reason,
        )
        _notice_settled(context)
        return
    context.state.set(PARK_NOTICE, owed)


def _notice_settled(context: _LateContext) -> None:
    """Drop the obligation, however it ended.

    One name for both endings, because the field records an obligation rather
    than an event: a sentence posted to the thread and a park retired or
    answered before anybody had to read it leave exactly nothing owed.
    """
    context.state.data.pop(PARK_NOTICE, None)


def _delivered_id(context: _LateContext, message: str) -> int | None:
    """The id of this notice's own comment on the thread, if it is there.

    The receipt a park notice has, since the post and the write that records
    it are two operations: a write that failed after a post that landed leaves
    pinned state claiming the opposite of what the issue holds, and the issue
    is the one of the two that cannot be wrong about what was said.

    The whole comment is matched rather than a marker, because a park notice
    carries none of its own: the sentence IS the identity, and it is one this
    mode built rather than anything a reader can shorten. The mention prefixed
    to it is not required to match, so the same reconciliation answers for a
    notice however the shared park decorated it.

    And the receipt has to be OURS. That the sentence is its own identity is
    exactly what makes the author load-bearing: it is plain text on a public
    thread, so anybody can paste it back, and read from anybody it would
    discharge an obligation nobody discharged. The park would stand with its
    notice marked said, the watermark would be dragged past whatever else an
    outsider had written under it, and the human the park was taken for would
    never be told -- on this tick and on every tick after it, since nothing
    supersedes a park like the spent-budget one. So the author goes through
    the same owner every other receipt this repository reads off a thread does
    (`github.comments.authored_by_us`), and a client with no authenticated
    login of its own to compare against falls back to the text alone exactly
    as those do.

    The highest match is the one reported, so what the watermark is repaired to
    is the last thing said rather than the first.

    A read that could not be taken answers None, which is the safe direction:
    the notice stays owed and is said again, which costs one repeated comment
    and never a silence.
    """
    try:
        thread = context.gh.comments_after(
            context.issue, context.state.get(_LAST_ACTION_COMMENT_ID),
        )
    except Exception:
        log.exception(
            "issue=#%d could not be read for a park notice already posted; "
            "leaving it owed rather than assuming it was said",
            context.issue.number,
        )
        return None
    bot_login = getattr(context.gh, "_bot_login", None)
    said = [
        issue_comment.id
        for issue_comment in thread
        if message in (issue_comment.body or "")
        and authored_by_us(issue_comment, bot_login=bot_login)
    ]
    return max(said) if said else None


def _fits_beside_the_state(context: _LateContext, owed: dict) -> bool:
    """Whether the pinned comment would still fit carrying this notice.

    Measured on the whole comment the write would produce rather than on the
    notice alone, through the same budget a recorded outcome is refused past,
    because the comment is shared and what is already in it counts.
    """
    return _late_session._fits_the_comment(
        {**context.state.data, PARK_NOTICE: owed},
        _late_session.MAX_RECORDED_BODY,
    )
