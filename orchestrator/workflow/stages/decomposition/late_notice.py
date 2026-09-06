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

Which is why a sentence explaining a RECORDED outcome names that record
instead of copying it. The explanation a `single` gave is already in this
comment; a notice repeating it would put the same agent prose in the same
comment twice, so an explanation an outcome could be recorded with would be
one its own obligation could not be written beside -- and the sentence lost
would be the only thing that would ever tell a human what their unpublished
candidate is waiting on. So the obligation holds a marker where the
explanation goes, sized by this owner's wording rather than by an agent's, and
what reaches the thread has it put back -- once, by the step that delivers it,
since every step between carries the obligation as stored and an explanation
naming this very marker would otherwise be expanded as though this owner had
written it. It is put back for that ONE park and no other: every other park's
sentence is an agent's or a human's text carried verbatim, and rewriting one
because it happens to contain the marker would put words in their mouth.

What goes back in is FENCED rather than escaped, and it goes in last. Those
are two defences against one hazard, and they buy different things. A thread
is markdown, so an explanation opening an HTML comment -- `<!--` anywhere in
it, this orchestrator's own pinned-state marker included -- swallows
everything after it: quoting LAST is what keeps that from costing a human the
instruction, and FENCING is what keeps it from costing them the rest of the
quote, since inside a block that text is shown rather than obeyed. The block
costs the same handful of characters however long the quote is, where escaping
every opener grows the comment per occurrence and an explanation the record
can hold is enough of them to push it past what GitHub accepts.

Which character the fence is built out of follows from the quote: markdown
blocks with backticks or with tildes, a run of one is nothing to the other,
and taking whichever the quote leaves cheap keeps the fence a handful of
characters even around an explanation that is itself a long run of fences.

What no fence answers is the quote that is a long run of BOTH characters,
which leaves neither one cheap and comes to twice itself blocked off. That
one goes in unblocked -- and then the openers inside it are ESCAPED, one
character apiece, because unblocked is exactly where they are obeyed again.
Quoting last keeps an opener from costing a human the instruction; only the
escape keeps it from costing them the rest of the explanation, which is the
one thing this park exists to deliver.

Both answers are bounded, and the room for the more expensive of them is
reserved where the outcome is accepted (`late_session`), the same way the
room its durable obligation needs already is. So nothing here is ever trimmed
to fit and nothing is stood in for: a fraction of a reason reads as the whole
of one, and a sentence about the explanation is not the explanation.

Nothing is rewritten inside that block. The text is the agent's, so what keeps
a sentence carrying the pinned-state marker findable on the thread afterwards
is the read that names the pinned comment by identity, which is what the body
test was standing in for.

The room that write needs is reserved where the outcome is accepted
(`late_session`), so a `single` this binary recorded always leaves it. What
the sentence may not be charged for is a record that costs more than that
reserve assumed without ever having broken it -- one an older binary wrote
against the whole outcome budget and reserved nothing out of, and one written
before the payload escaped the wrapper's own terminator, which renders larger
today than on the tick that measured it. Neither is anything the sentence did
and neither is anything a later tick can undo, so the reserve is granted on
top of what the record actually costs and the one hard bound is the size a
write really fails at.

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
import re

from orchestrator.github.comments import authored_by_us
from orchestrator.github.pinned_state import MAX_PINNED_BODY, pinned_state_body
from orchestrator.workflow.stages.decomposition import (
    late_session as _late_session,
)
from orchestrator.workflow.stages.decomposition.late_models import (
    UNRECORDED_SPLIT_BLOCKER,
    _LateContext,
    _StagedPark,
)

log = logging.getLogger("orchestrator.workflow")

# The notice a park recorded here has still to say out loud. Spelled with the
# mode's own prefix because it is this mode's obligation: another stage's park
# is not one this owner may speak for.
PARK_NOTICE = "late_park_notice"

# What a notice writes where it means the explanation the record already
# holds. A sentence that copied that prose instead would put the same agent
# text in the same comment twice, so an explanation the outcome could be
# recorded with would be one its own obligation could not be written beside --
# and the parks these sentences explain are the ones nothing supersedes, so
# what that costs is a human never told at all.
#
# Named rather than searched for: the wording puts it where the explanation
# goes, because a short explanation is a substring of the sentence around it
# and a search would find the wrong one.
#
# Deliberately NOT an HTML comment, which is what every marker this
# orchestrator writes onto a THREAD is. This one is written into the pinned
# comment, and that comment is itself an HTML comment: a sentinel carrying
# `-->` would close it early, and GitHub would render the rest of the payload
# -- the recorded result, the recovery fields, everything after it -- as
# visible issue text. So it is a bracketed token, which JSON carries verbatim
# and HTML has no opinion about.
RECORDED_EXPLANATION = "{{orchestrator-late-explanation}}"

# What the shortest fence is, the two characters markdown builds one out of,
# and how a run of each is found. A thread is markdown, so an explanation is
# put in a fenced block: inside one, text opening an HTML comment is shown
# rather than obeyed, which is the whole point -- an agent writing `<!--`
# anywhere would otherwise swallow the rest of the sentence, and a human would
# be told neither what it said nor what to do about it. Escaping the openers
# instead grows the comment per occurrence, which an explanation the record
# can hold is enough of to push past what GitHub accepts; a fence costs the
# same handful of characters however long the quote is.
#
# A fence has to be longer than any LINE inside it that could close it, and a
# line closes one only by being a run of the fence character and nothing else
# -- a run in the middle of a line closes nothing. Which is why both
# characters are kept rather than one: a line of backticks cannot close a
# tilde fence at all, so the explanation that would cost a backtick fence a
# copy of itself at each end costs a tilde fence three characters. The
# backtick comes first, so a quote that leaves both cheap is blocked off by
# the ordinary one.
_SHORTEST_FENCE = 3

_FENCE_CHARACTERS = ("`", "~")

# What ends a line, for markdown and so for a fence. A quote is split on all
# of them and rejoined by the ones it arrived with, because an explanation
# written on a machine that ends its lines with a carriage return is still an
# explanation whose fence lines close a block -- and reading only the newline
# would block such a quote off at three characters it carries.
_LINE_ENDINGS = ("\n", "\r")

_FENCE_LINE = re.compile(r"\A[ \t]*(`+|~+)[ \t]*(?:\r\n|[\n\r])?\Z")

# And what to do where neither character is cheap, which is the quote carrying
# a long line of each: the quote is BLOCKED OFF IN PIECES rather than in one.
# A fence costs two characters for every character of width and a further
# block costs a fixed handful, so the two trade against each other -- a wide
# fence buys one block for a quote whose lines are wide, and many narrow
# blocks buy a narrow fence for a quote whose wide lines are few.
#
# Which way round is not something a rule of thumb gets right: a quote of
# eight-character fence lines wants ONE block nine characters wide, and a
# quote of two enormous ones wants three blocks three characters wide, and a
# greedy that splits whenever a widening looks dear picks the first badly. So
# every width from the shortest fence up to the widest line is tried by
# doubling, and the smallest rendering wins. Each pass is one walk of the
# lines and there are as many passes as the quote has doublings, which is
# nothing beside what it costs to be wrong.
_CAP_STEP = 2

# What OPENS an HTML comment on a thread, and how it is written where the
# quote carrying it is not blocked off. Inside a block that text is shown
# rather than obeyed and nothing is rewritten; outside one it is obeyed, and
# GitHub renders nothing from the opener onwards -- which on this park costs a
# human the tail of the only explanation they will ever be given.
#
# The escape is a backslash, which is one character and the cheapest markdown
# has: what follows the `<` is then an escaped `!` rather than the opener's
# own, so no HTML comment is recognized and the four characters render exactly
# as the agent wrote them. Escaping every `<` instead, or writing the entity
# for it, costs three or more apiece, and an explanation the record can hold
# is enough of them to push the comment past what GitHub accepts.
_COMMENT_OPEN = "<!--"

_ESCAPED_COMMENT_OPEN = r"<\!--"

# What a human is told where no rendering of an explanation fits one comment.
# Nothing this binary records reaches it -- an outcome is held to a budget
# that leaves the room, and blocking a quote off in pieces costs a handful of
# characters even for a quote built to defeat a single fence. What it answers
# is the one failure with no recovery at all: a notice GitHub refuses is
# rebuilt identically on every poll, so the park stands and the human is never
# told anything.
_CUT_QUOTE = "\n\n(cut: no rendering of the whole explanation fits one comment)"

# The one park whose sentence names that record. Spelled here rather than
# imported for the reason `_PARK_REASON` below is: reaching back into the
# owner that stages parks would make this leaf part of the cycle it sits
# under. What it buys is that the substitution is scoped to the sentence this
# owner worded -- every other park's sentence is an agent's or a human's text
# carried verbatim, and one that happens to contain the marker is theirs to
# have written, not this owner's to expand.
_NAMES_THE_EXPLANATION = "late_single_decision"

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
    everything downstream -- the obligation as it is stored, marker and all.
    Rendering it is the delivering step's own, and asked exactly once there,
    because a sentence expanded twice is not the sentence that was posted.

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


def _filled(context: _LateContext, owed: _StagedPark) -> str:
    """Put the recorded explanation back into a notice that named it.

    The other half of naming it rather than copying it. Asked ONCE per road a
    sentence takes, and never of what it returns: the two places a rendered
    notice is needed are the post and the thread reading that looks for it,
    and each asks for itself. What is carried between the steps in between --
    on the tick, and on the pinned comment -- is the obligation as it is
    stored, so no road can expand what a previous step already expanded.

    Scoped by the park it explains, because only one park's sentence is worded
    by this orchestrator with a place left in it. Every other park carries an
    agent's or a human's text verbatim -- a categorized question quotes what
    the agent asked -- so one that happens to contain the marker wrote it
    itself, and rewriting it would put words in somebody's mouth and leave the
    posted sentence unfindable on the thread.

    Inside that scope, replacement does not re-scan what it inserts, so one
    pass leaves an explanation's own marker text exactly where the agent wrote
    it; two passes would expand it as though this owner had put it there, and
    the sentence posted and the sentence looked for would stop being the same
    one.

    A record with no explanation on it answers with the same stand-in every
    other reader of a `single` gets. Reaching that is a record something
    dropped out from under a park still owing its sentence, and telling a
    human no reason was recorded is the true answer to it.

    What goes in is FENCED rather than escaped. A thread is markdown, so an
    explanation opening an HTML comment would swallow the rest of the sentence
    and leave a human reading as far as the quote -- told neither what the
    agent said nor what to do about it. Inside a fence that text is shown
    rather than obeyed, and the fence costs the same handful of characters
    however long the quote is, where escaping the openers grows the comment
    per occurrence and an explanation the record can hold is enough of them to
    push it past what GitHub accepts.

    The whole of it goes in, whatever that costs the rendering. An
    explanation that is a long run of BOTH fence characters leaves neither one
    cheap, and no comment could hold the block that would go around it -- so
    that quote goes in unblocked, with its HTML-comment openers escaped. It is
    the block that gives way and never a word of the explanation: this park is
    one nothing supersedes, its sentence is the only thing that will ever say
    what stopped a split, and a piece of a reason reads as the whole of one.

    The escape is only for the unblocked road, and it is what makes that road
    an answer at all. Inside a block an opener is shown rather than obeyed;
    outside one GitHub renders nothing from it onwards, so an explanation that
    defeated the fence AND opened a comment would reach the thread with its
    tail invisible -- present in the body and gone from the page, which is not
    a human being told. Both roads fit because the room the dearer of them
    needs is reserved where the outcome was accepted.

    Nothing else is rewritten. A sentence carrying this orchestrator's own
    pinned-state marker is left as its author wrote it, and what keeps it
    findable afterwards is the reader below.
    """
    if owed.reason != _NAMES_THE_EXPLANATION:
        return owed.message
    if RECORDED_EXPLANATION not in owed.message:
        return owed.message
    recorded = _late_session._recovered_adjudication(
        _late_session._read_late_run(context.state),
    )
    return owed.message.replace(
        RECORDED_EXPLANATION,
        _quoted(recorded.split_blocker_explanation or UNRECORDED_SPLIT_BLOCKER),
    )


def _quoted(explanation: str) -> str:
    """This explanation as a comment can carry it, whole and visible.

    Blocked off where a comment can hold the blocks, because inside one an
    opener is shown rather than obeyed and nothing at all is rewritten. The
    quote built to defeat that -- a long fence line of each character -- is
    answered by blocking it off in pieces rather than by saying less of it.

    Unblocked otherwise, with the HTML-comment openers escaped, since
    unblocked is exactly where an opener is obeyed again: GitHub renders
    nothing from it onwards, so an explanation that reached the thread raw
    would be in the comment body and off the page, which is not a human being
    told.

    Cut only where neither fits, which nothing this binary records can reach:
    the outcome budget leaves the room and the pieces cost a handful of
    characters. It is here because the alternative has no recovery -- a
    comment GitHub refuses is rebuilt identically on every poll, so the park
    stands with its sentence owed and the human is told nothing at all, for
    good. A cut quote says so where it was cut.
    """
    blocked = _quoted_block(explanation)
    if len(blocked) <= _late_session.MAX_QUOTED_BLOCK:
        return blocked
    shown = explanation.replace(_COMMENT_OPEN, _ESCAPED_COMMENT_OPEN)
    if len(shown) <= _late_session.MAX_QUOTED_BLOCK:
        return shown
    log.error(
        "no rendering of a %d-character split-blocker explanation fits one "
        "comment; cutting the quote so the park's sentence can be said at all",
        len(explanation),
    )
    room = _late_session.MAX_QUOTED_BLOCK - len(_CUT_QUOTE)
    return shown[:room] + _CUT_QUOTE


def _quoted_block(quoted: str) -> str:
    """This text between fences no line inside one can close.

    A fence is longer than any line in the block that could close it, because
    markdown ends a fenced block on a line that is a run of the fence
    character and nothing else -- so a quote carrying a fence of its own would
    otherwise close this one early and let everything after it render as
    markdown again, which is the failure the fence is here to prevent. A run
    in the MIDDLE of a line closes nothing, which is what keeps the fence a
    handful of characters around prose that merely mentions one.

    Which character it is built out of follows from that: a line of backticks
    cannot close a tilde fence, so the cheaper of the two is taken. That
    answers the explanation that is a long run of ONE character; the one that
    carries a long line of EACH is answered by blocking the quote off in
    pieces, since a fence is two characters per character of width and a
    further block is a fixed handful.

    How wide to let a fence grow before paying for a block instead is the
    whole of it, and it is answered by trying: every width from the shortest
    fence up to the widest line the quote carries, doubling, and the smallest
    rendering wins. A quote of narrow fence lines wants one wide block and a
    quote of two enormous ones wants three narrow blocks, and nothing local to
    a line tells them apart.
    """
    lines = quoted.splitlines(keepends=True)
    closings = [_closing_lengths(line) for line in lines]
    return min(
        (_blocked_at(lines, closings, cap) for cap in _fence_caps(closings)),
        key=len,
    )


def _fence_caps(closings: list[tuple[int, int]]) -> list[int]:
    """The fence widths worth blocking a quote off at.

    From the shortest fence markdown has to the widest line in the quote,
    doubling: below the first nothing is legal and above the last nothing is
    bought, and between them the doublings bracket whatever the best answer
    is closely enough that the rendering they miss is a handful of characters
    rather than a copy of the quote.
    """
    widest = max(
        (max(closing) for closing in closings), default=0,
    ) + 1
    caps = []
    cap = _SHORTEST_FENCE
    while cap < widest:
        caps.append(cap)
        cap *= _CAP_STEP
    caps.append(max(widest, _SHORTEST_FENCE))
    return caps


def _blocked_at(
    lines: list[str], closings: list[tuple[int, int]], cap: int,
) -> str:
    """This quote in blocks, none of them fenced wider than `cap`.

    A line that would widen the fence past the cap starts a fresh block
    instead, and every block is fenced at its own width rather than the cap's
    -- so a cap that is never reached costs one block and nothing else.
    """
    blocks = []
    held: list[str] = []
    closes = (0, 0)
    for line, closing in zip(lines, closings, strict=True):
        if held and len(_fence_of(_widened(closes, closing))) > cap:
            blocks.append(_walled(held, closes))
            held = []
            closes = (0, 0)
        held.append(line)
        closes = _widened(closes, closing)
    blocks.append(_walled(held, closes))
    return "\n".join(blocks)


def _widened(
    closes: tuple[int, int], closing: tuple[int, int],
) -> tuple[int, int]:
    """The longest closing run of each character, with one more line in it."""
    return tuple(
        max(so_far, added)
        for so_far, added in zip(closes, closing, strict=True)
    )


def _closing_lengths(line: str) -> tuple[int, int]:
    """How long a fence of each character this ONE line could close.

    A line closes a block only by being a run of the fence character with
    nothing else on it, so this answers zero for every line that merely
    carries a run -- which is most of them, and why an explanation that talks
    about fences is still blocked off by three characters.

    Leading and trailing whitespace is allowed around the run rather than
    refused, because markdown allows it on a closing fence and reading it as
    harmless would be the reading that lets a quote close its own block. The
    line ENDING is allowed for the same reason and matters more: the line
    arrives with the terminator it was written with, and markdown ends a line
    on a carriage return as readily as on a newline -- so a run followed by
    `\r\n` or by a bare `\r` is a closing fence, and one read as ordinary
    text would be blocked off by three characters it could close.
    """
    matched = _FENCE_LINE.match(line)
    if matched is None:
        return (0, 0)
    run = matched.group(1)
    if run.startswith(_FENCE_CHARACTERS[0]):
        return (len(run), 0)
    return (0, len(run))


def _fence_of(closes: tuple[int, int]) -> str:
    """The shortest fence no line closing at these lengths can close.

    One character longer than the run it has to survive, and the cheaper of
    the two characters, with the tie going to the backtick -- which is the
    ordinary one and so the one a quote that carries neither is blocked off
    by.
    """
    widths = tuple(
        max(_SHORTEST_FENCE, closing + 1) for closing in closes
    )
    if widths[0] <= widths[1]:
        return _FENCE_CHARACTERS[0] * widths[0]
    return _FENCE_CHARACTERS[1] * widths[1]


def _walled(lines: list[str], closes: tuple[int, int]) -> str:
    """These lines between one fence they cannot close.

    Joined by the terminators they arrived with rather than by a newline this
    owner picks, so an explanation written with carriage returns reaches the
    thread as its author wrote it. The closing fence needs a line of its own,
    which the last line supplies unless it ended without one.
    """
    fence = _fence_of(closes)
    body = "".join(lines)
    if not body.endswith(_LINE_ENDINGS):
        body = f"{body}\n"
    return f"{fence}\n{body}{fence}"


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

    Whether it fits is measured on the whole comment the write would produce,
    because that comment is shared and what is already in it counts. What it
    is measured beside is the record WITHOUT any obligation already on it,
    since a notice replaces one rather than joining it. A notice that NAMES
    the recorded explanation is measured at the size it is stored at, which is
    this owner's own wording, so no agent's prose can put it past that.

    The ceiling is `MAX_NOTICE_COMMENT`, which is the whole of what a recorded
    outcome may take plus the room reserved BESIDE it for the sentence the
    park it earns owes -- beside rather than inside, since measuring a notice
    against the outcome's own budget would charge it twice.

    A record on a live issue can cost more than that budget without ever
    having broken it, in two ways that are the same way: one an older binary
    wrote was held to the whole outcome budget and reserved nothing out of it,
    and one written before the payload escaped the wrapper's own terminator
    (`github.pinned_state`) renders five characters longer per `-->` today
    than on the tick that measured it -- an agent's explanation and a
    preserved pull-request body both carry those. Neither is anything the
    sentence did, and neither is anything a later tick can undo: the record is
    durable, and every write of this issue carries it. Refused for either, a
    park nothing supersedes would drop the obligation its retry depends on,
    and the human would never be told what their unpublished candidate is
    waiting on. So the reserve is granted on top of what the record actually
    costs, and the one hard bound is the size a write really fails at: a
    comment longer than GitHub accepts is one that cannot be written, and the
    write it would take down is the park's.
    """
    record = {
        key: held
        for key, held in context.state.data.items()
        if key != PARK_NOTICE
    }
    owed = {_REASON: staged.reason, _MESSAGE: staged.message}
    ceiling = min(
        max(
            _late_session.MAX_NOTICE_COMMENT,
            len(pinned_state_body(record)) + _late_session.MAX_NOTICE_BODY,
        ),
        MAX_PINNED_BODY,
    )
    if not _late_session._fits_the_comment({**record, PARK_NOTICE: owed}, ceiling):
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


def _delivered_id(context: _LateContext, owed: _StagedPark) -> int | None:
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

    Taken from the OBLIGATION as it is stored, and rendered here: what is on
    the thread is a sentence with whatever it names put back, and this is the
    one place on this road that puts it back. A caller that rendered it first
    would have this expand it a second time, and an explanation naming the
    marker itself would then stop matching the comment it was posted as.

    The thread is read with the pinned comment named by its IDENTITY rather
    than found by the marker in its body. A notice quoting an agent who wrote
    that marker -- an explanation about this orchestrator's own state comment
    -- reads as a state comment to the body test, so the one comment this is
    looking for would be the one comment it could not see, and the sentence
    would be said again on every tick after the write recording it was lost.
    Escaping the marker out of the sentence would answer that too, and it is
    the wrong answer: it grows the comment per occurrence, and an explanation
    the record can hold is one such a rewrite can push past what GitHub
    accepts -- a notice no tick could deliver at all.

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
            context.issue,
            context.state.get(_LAST_ACTION_COMMENT_ID),
            state_comment_id=context.state.comment_id,
        )
    except Exception:
        log.exception(
            "issue=#%d could not be read for a park notice already posted; "
            "leaving it owed rather than assuming it was said",
            context.issue.number,
        )
        return None
    bot_login = getattr(context.gh, "_bot_login", None)
    delivered = _filled(context, owed)
    said = [
        issue_comment.id
        for issue_comment in thread
        if delivered in (issue_comment.body or "")
        and authored_by_us(issue_comment, bot_login=bot_login)
    ]
    return max(said) if said else None
