# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one command that moves an issue off its spent agent-run ledger.

The park beside this owner is the whole ending of an issue that has spent its
lifetime: no clock returns a run, and every stage road below reads
`awaiting_human` as something else. What is left is a human deciding this
issue is worth more runs than it was allowed, and this is where that decision
is written down.

`/orchestrator add-agent-runs N` is that decision and nothing else. It is read
only while the park stands, because the park is the only thing it can lift: on
a running issue it would be a ceiling nobody was held to, and on any other
park it would answer a question it was not asked. It is read only from a
trusted author, because what it buys is agent time on somebody's word -- the
same allowlist every other workflow-driving comment on a public thread goes
through. And it is read only as an exact positive whole number no larger than
`MAX_RUNS_PER_COMMAND`, because the number IS the command: a slip of the
keyboard that reads as a thousand runs is not a decision anybody took.

What a valid command buys is an allowance of exactly `used + N` -- the runs
already spent plus the ones just granted -- rather than a count added onto
whatever the field said before. Written that way it says the same thing
however often it is read: nothing spends a run while the park stands, so a
tick that dies between the receipt and the write grants the same ceiling again
on the next one rather than a second N on top of it.

Everything else is refused rather than acted on, and refused the same way: the
park stands, the ledger is left exactly where the request found it, and the
thread is told what a request has to say. Both answers carry a marker scoped
to the comment that asked, because a post and the write that consumes what it
answers cannot be made one operation -- so the thread is read before either
sentence is written again, exactly as every other receipt in this repository
is. An untrusted account is answered with nothing at all: a reply is a comment
somebody else's word paid for, and consuming the thread for one would spend
the watermark a trusted operator's command is read against.

The command is also a line the drift hash has to know about, which is why the
reading that recognizes it is published here rather than kept inside. An
answered command hands the SAME tick to the stage the label names, so a hash
counting it would put that handler in front of a body nobody edited and call
it changed requirements -- a developer resumed where a reviewer was owed a
round. What is control is the command ALONE; words beside it are requirements
and travel the drift road that carries them to an agent.

Neither ending returns a run. What the ledger has spent is spent, and both
counts stay where they were: this widens what an issue may spend, and there is
nothing here that unspends anything.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.github.comments import carries_own_marker, filter_trusted
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import (
    comments as _comments,
    run_ledger as _run_ledger,
    run_limit as _run_limit,
)

log = logging.getLogger("orchestrator.workflow")

# The most one command may buy. A bound is what keeps a decision a decision:
# a typo costs at most this many runs, and a human who wants more says so
# again -- which is one more sentence on the record rather than one unbounded
# number nobody reads twice. It is a property of the command rather than of
# the deployment, so it does not move when `MAX_AGENT_RUNS_PER_ISSUE` does and
# it still bounds a request on an issue whose ceiling is off.
MAX_RUNS_PER_COMMAND = 50

# The command, as a whole line of its own. Anchored at both ends so the
# receipts below -- which spell it inside a sentence, quoted -- are not read
# back as requests. The argument is captured as whatever was written rather
# than as a number, because a malformed one is a request this owner owes an
# answer to and not a line it never saw.
_ADD_RUNS_RE = re.compile(
    r"^[ \t]*/orchestrator[ \t]+add-agent-runs"
    r"(?P<count>[ \t]+[^\r\n]*?)?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

# What the argument has to be: digits and nothing else. `int()` would take a
# sign, a surrounding space, and a unicode digit nobody typed on purpose, and
# a command whose number is guessed at is a ceiling nobody chose.
_COUNT_RE = re.compile(r"[0-9]+")

# How many digits a number this command can act on is written in. The bound
# above is the reason it exists, but the length is checked BEFORE the digits
# are converted: `int()` refuses a string past the interpreter's own
# conversion limit by raising, and a request that raises is one nobody is
# answered about -- neither granted nor refused, on a park that goes on
# standing. So a count too long to be inside the bound is turned away as the
# excessive request it is, without being converted at all.
_MAX_COUNT_DIGITS = len(str(MAX_RUNS_PER_COMMAND))

# Stamped on the answer one request earns, whichever answer it is, and scoped
# to the comment that carried it. A second request is a second decision and
# owes its own sentence, while an unscoped marker would read the first answer
# as the answer to every request after it. Both are HTML comments, so they are
# invisible in the rendered thread -- and both are what makes an answer
# idempotent: the comment and the write that consumes the request it answers
# cannot be made one operation, so the thread is read for the receipt before
# it is written a second time.
_REFUSED_MARKER = (
    "<!--orchestrator-add-agent-runs-refused"
    ":issue={issue}:comment={comment}-->"
)

_GRANTED_MARKER = (
    "<!--orchestrator-add-agent-runs-granted"
    ":issue={issue}:comment={comment}-->"
)

_REFUSAL_NOTICE = (
    "{mentions} that `/orchestrator add-agent-runs` request is not one this "
    "park can act on: it takes a whole number of runs from 1 to {maximum}, "
    "on a line of its own. Nothing moved -- this issue's allowance and the "
    "runs spent against it are exactly where they were, and it is still "
    "parked. Say it again with a count in that range.\n\n{marker}"
)

_GRANT_NOTICE = (
    ":arrows_counterclockwise: granting {added} more agent run(s): this "
    "issue's lifetime allowance is now {allowance}, against {used} already "
    "spent. What was spent stays spent -- this widens the ceiling rather than "
    "returning a run -- so the issue stops here again once it reaches "
    "it.\n\n{marker}"
)

_AWAITING_HUMAN = "awaiting_human"

_PARK_REASON = "park_reason"

_LAST_ACTION_COMMENT_ID = "last_action_comment_id"


@dataclass(frozen=True)
class _Request:
    """One `add-agent-runs` command, the comment that carried it, and what it
    buys.

    The comment is part of the request because the receipt written for it --
    a grant's or a refusal's -- is scoped to that comment: what a marker has
    to tell apart is one request from the next, and the argument alone cannot,
    since two people asking for the same thing are still two decisions.

    `added` is None for a request nothing can be bought with, which is the
    whole of what "malformed" means here. It is settled where the line is read
    rather than where it is acted on, so both roads below are handed one
    record that already knows which of the two it is.

    `consumed` is the last comment of the batch this request was read out of,
    and it is carried rather than looked up again for the same reason: what a
    tick may mark answered is what it READ, and a thread re-read for a
    boundary would hand back comments nobody here has seen.
    """

    asked: str
    comment_id: int
    added: int | None
    consumed: int


def _lifts_the_park(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> bool:
    """Whether a human has just bought this issue past its spent ledger.

    True means the park is down, the grant is durable, and the tick may go on
    to the stage its label names -- which is the point of answering here
    rather than leaving the command for the next poll: the run a human paid
    for is the one this issue was stopped for.

    False is every other reading, and the caller holds the tick on all of
    them: no command on the thread, an untrusted one, a request this park
    cannot act on (which earns its receipt on the way past), and a thread that
    could not be read at all. Those last two are not symmetric with a grant --
    a park held one poll too long is answered by the next read, while a grant
    handed out on a thread nobody could read buys runs no human asked for.

    The park is asked for again here rather than taken from the caller,
    because it is the whole of what this command may touch: what it lifts is
    an issue held on a spent ledger, and read anywhere else the same words
    would clear a park waiting for something they do not say -- or hand a
    running issue a ceiling nobody decided.

    A park that still owes the thread its sentence is left alone. The hold
    above says that sentence, and saying it moves the response boundary past
    everything written under the old one -- so a command read here would be a
    command written before the question was put, bought and then consumed by
    the notice explaining why the issue had stopped.
    """
    unanswerable = (
        not _run_limit._park_stands(state)
        or _run_limit._owed_notice(state) is not None
    )
    if unanswerable:
        return False
    try:
        thread = gh.comments_after(issue, state.get(_LAST_ACTION_COMMENT_ID))
    except Exception:
        log.exception(
            "issue=#%d could not be read for the command that buys it more "
            "agent runs; holding the park this tick",
            issue.number,
        )
        return False
    request = _requested(filter_trusted(thread))
    if request is None:
        return False
    if request.added is None:
        _refuse_request(gh, issue, state, request, thread)
        return False
    _grant_runs(gh, issue, state, request, thread)
    return True


def _is_bare_command(issue_comment: Any) -> bool:
    """Whether this comment is the command and nothing else.

    Asked by the drift hash rather than by anything here. A command is an
    operator CONTROL, not a line of requirements: counted as content it would
    shift the hash on the very tick the park comes down, and the handler the
    grant hands the issue to would read a body nobody edited as changed
    requirements -- resuming a developer where a reviewer was owed a round.

    Bare is the whole test, for the reason `/orchestrator continue` is held to
    the same one: a comment that carries the command ALONGSIDE guidance is
    guidance, it moves the hash, and the drift road it opens is how those
    words reach the agent that has to act on them.
    """
    written = (getattr(issue_comment, "body", "") or "").strip()
    return _ADD_RUNS_RE.fullmatch(written) is not None


def _requested(comments: list) -> _Request | None:
    """The last `add-agent-runs` command the unread thread carries.

    The last rather than the first, because a batch is read in thread order
    and a human who wrote the command twice meant the second one. Several
    lines in one comment read the same way, so a corrected count below a typo
    is the request rather than the line it corrects.

    What the record carries out of here is the whole batch as well as the
    command: the words a human wrote above or below it are read by this tick
    too, and answering the command is answering them. The batch ends at the
    last TRUSTED comment, since that is all this owner is handed -- an
    outsider's is left where it is for the next tick to filter out again.
    """
    latest = None
    for comment in comments:
        for found in _ADD_RUNS_RE.finditer(comment.body or ""):
            latest = ((found.group("count") or "").strip(), comment.id)
    if latest is None:
        return None
    asked, comment_id = latest
    return _Request(
        asked=asked,
        comment_id=comment_id,
        added=_added_runs(asked),
        consumed=max(read.id for read in comments),
    )


def _added_runs(asked: str) -> int | None:
    """How many runs one request buys, where what it asks for buys any.

    None for every other reading, and the same None for all of them: a missing
    count, a word, a sign, a fraction, a zero, and a number past the bound end
    in one place -- a park that stands and a thread that is told what a
    request has to say. What separates them is the human's own comment, which
    is still on the thread right above the receipt.

    The leading zeros go before the length is measured, so `007` is the seven
    somebody wrote and a thousand digits is a number no bound could hold. That
    order is what keeps the count out of `int()` until it is known to be
    short: the interpreter refuses to convert a long enough digit string at
    all, and a request that RAISES is one nobody is answered about -- not
    granted, not refused, on a park that goes on standing.

    A zero falls out of the same step rather than being tested for. Every
    digit of it is a leading one, so what is left of `0` or `000` is nothing
    at all -- which is exactly what a request naming no runs buys.
    """
    if not _COUNT_RE.fullmatch(asked):
        return None
    counted = asked.lstrip("0")
    if not counted or len(counted) > _MAX_COUNT_DIGITS:
        return None
    added = int(counted)
    if added > MAX_RUNS_PER_COMMAND:
        return None
    return added


def _grant_runs(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    request: _Request,
    thread: list,
) -> None:
    """Buy this issue the runs one request asks for, and take its park down.

    The allowance is written as the whole number this issue may spend rather
    than as an increment onto the field, because that is what the ledger holds
    and what makes a replayed grant harmless: the count spent has not moved
    while the park stood, so the same command read twice writes the same
    ceiling twice.

    Said once per REQUEST rather than once per tick, for the reason the
    refusal beside it is: the acknowledgement and the write that consumes the
    command cannot be made one operation, so a tick that died between them
    reads the same command again -- and the marker its own receipt carries is
    what keeps that second reading from saying the same sentence twice.

    An obligation is dropped on the way out. There is none to drop on a park
    whose sentence was said, which is the only kind that reaches this -- but a
    record left in a shape nothing can read is one the park it belonged to no
    longer has, and the park is what is ending here.

    Nothing gives a run back. What is spent stays spent, and the issue stops
    on this same park the moment it reaches the ceiling this bought it.
    """
    ledger = _run_ledger._read_ledger(state)
    allowance = ledger.used + request.added
    log.info(
        "issue=#%d was granted %d more agent run(s) by a trusted operator "
        "command; its lifetime allowance is now %d against %d spent",
        issue.number, request.added, allowance, ledger.used,
    )
    marker = _GRANTED_MARKER.format(
        issue=issue.number, comment=request.comment_id,
    )
    _said(gh, issue, state, thread, (marker, _GRANT_NOTICE.format(
        added=request.added,
        allowance=allowance,
        used=ledger.used,
        marker=marker,
    )))
    state.set(_run_ledger.AGENT_RUN_ALLOWANCE, allowance)
    state.set(_AWAITING_HUMAN, False)
    state.set(_PARK_REASON, None)
    _run_limit._settle_notice(state)
    _consumed(gh, issue, state, request, _run_limit.RunLimitPhase.GRANTED)


def _refuse_request(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    request: _Request,
    thread: list,
) -> None:
    """Tell the thread what a request has to say, once, and stay parked.

    Once per REQUEST rather than once per tick, by the same receipt the grant
    beside this one writes: the marker is scoped to the comment that asked,
    and the thread is read for it before the sentence is written again.

    Nothing is charged and nothing is bought. The allowance and the runs spent
    against it are exactly what they were, which is what the sentence tells a
    human: this is a request that was not acted on, rather than a grant of
    some other size.
    """
    log.info(
        "issue=#%d asked for more agent runs in a request this park cannot "
        "act on; leaving the ledger where it was and saying so",
        issue.number,
    )
    marker = _REFUSED_MARKER.format(
        issue=issue.number, comment=request.comment_id,
    )
    _said(gh, issue, state, thread, (marker, _REFUSAL_NOTICE.format(
        mentions=config.HITL_MENTIONS,
        maximum=MAX_RUNS_PER_COMMAND,
        marker=marker,
    )))
    _consumed(gh, issue, state, request, _run_limit.RunLimitPhase.REFUSED)


def _said(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    thread: list,
    said: tuple[str, str],
) -> None:
    """Write one answer to the thread, unless the thread already carries it.

    `said` is the marker that identifies this receipt and the body carrying
    it. Both answers this owner writes go through here, because both are the
    visible half of a step whose durable half is a separate write: a tick that
    posts and then fails to record what it posted reads the same request again
    on the next poll, and what stops it saying the same sentence twice is the
    receipt already on the thread.

    Both halves of "ours" are asked of that receipt -- the scoped marker and
    the author -- since a marker is plain text anybody may paste, and read
    from anybody it would silence the answer a human is owed.
    """
    marker, body = said
    if carries_own_marker(
        thread, marker, bot_login=getattr(gh, "_bot_login", None),
    ):
        return
    _comments._post_issue_comment(gh, issue, state, body)


def _consumed(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    request: _Request,
    phase: _run_limit.RunLimitPhase,
) -> None:
    """Consume exactly what this tick read and answered, and record the tick.

    The mark moves to the last comment of the batch the request was read out
    of, and then over the answer written under it -- and no further. What it
    may never move over is a comment nobody here has seen: the thread is read
    once, the receipt is written after that read, and a human who commented in
    between would be marked answered by a tick that never looked at their
    words. A watermark is how every stage below decides what is still unread,
    so a comment swept under it is not delayed, it is lost.

    It is ratcheted rather than set, so a mark already past what this tick saw
    is left where it is.

    The write is taken here rather than left to the caller, because both
    endings leave the tick: one returns to a hold that dispatches nothing, and
    the other to a stage handler that reads this issue's state back from the
    pinned comment. A grant that is not durable by then is a park the next
    read puts straight back.
    """
    consumed = state.get(_LAST_ACTION_COMMENT_ID)
    answered = _answered_through(gh, issue, state, request)
    if not isinstance(consumed, int) or answered > consumed:
        state.set(_LAST_ACTION_COMMENT_ID, answered)
    _run_limit._emit_phase(gh, issue, phase)
    gh.write_pinned_state(issue, state)


def _answered_through(
    gh: GitHubClient,
    issue: Issue,
    state: PinnedState,
    request: _Request,
) -> int:
    """The last comment this tick may claim to have answered.

    The batch the request was read out of, extended over the receipts written
    under it, and stopped by the first comment that is neither. Both halves
    matter. Without the extension the answer just posted stays unread, and the
    road a grant opens would find the orchestrator's own acknowledgement where
    it looks for a human's words. Without the stop, a comment somebody wrote
    between the read and the post -- the one window in which the thread can
    grow under this owner -- would be marked answered by a tick that never
    read it.

    Ours is settled by the id ledger the post itself records and, failing
    that, by the marker every comment this orchestrator writes carries, since
    a write that never landed leaves the id nowhere. Anything else stops the
    walk, whoever wrote it: what is at stake is somebody's unread comment, and
    a mark that stops one comment short costs a tick rather than a word.

    A thread that cannot be read answers with the batch alone. The receipt is
    then read back as a fresh comment by a later tick, which is what its
    marker and the id ledger are there to settle -- and far cheaper than a
    mark past comments nobody has read.
    """
    answered = request.consumed
    try:
        written = gh.comments_after(issue, answered)
    except Exception:
        log.exception(
            "issue=#%d could not be re-read for the answer just written to "
            "it; consuming the batch the command was read out of and leaving "
            "that answer for the next tick",
            issue.number,
        )
        return answered
    recorded = _comments._orchestrator_ids(state)
    bot_login = getattr(gh, "_bot_login", None)
    for posted in written:
        if posted.id not in recorded and not carries_own_marker(
            (posted,), _comments._ORCH_COMMENT_MARKER, bot_login=bot_login,
        ):
            break
        answered = posted.id
    return answered
