# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The park an adjudicated candidate with nobody behind it waits on.

What an oversized reading earns where `late_authority` beside this says the
exemption naming the candidate has no operator authorization standing behind
it. It is a HOLD rather than a route back to `workflow:decomposing`, and that
difference is the whole of what the compatibility is worth: the change has
already been ruled one change, so sending it back would pay for a second
adjudicator over an answered question and risk a `split` cutting children out
of work somebody decided ships whole. What is missing is a person, so the park
asks for one.

The COUNT is deliberately not made durable. A generation carrying a reading
past its ceiling is exactly what this workflow means by an adjudication in
flight -- the dispatcher restores `workflow:decomposing` over one before any
stage sees the issue, the coordinator owns every later tick, and a fresh
adjudicator is paid for -- so a park that recorded one would be relabelled out
from under itself on the next poll and nothing could ever answer it. What
stays on the comment is the pair the freeze already recorded, and the reading
is re-taken by the tick that acts, which is the tick an authorization's terms
have to be written from anyway.

Nothing is deleted, migrated, or repaired to take it. The exemption, the
identity beside it, the approval naming the commit a push is owed for, and
every other field are left exactly as found: the record is what an
authorization would be checked against, and a park that tidied the pinned
comment on the way would destroy the evidence it exists to ask about.

What ends it is a trusted whole-comment `/orchestrator authorize-oversized
<commit>` naming the parked candidate, which `late_command` reads. Acted on
HERE rather than at the gate's door because this is the only place holding a
reading: an operator authorizes a change of THIS size against THAT ceiling,
and the terms of the record are the pair this call froze, the additions it
counted, and the ceiling it counted them against.

Every notice is worded on the side of publication the park was taken on,
because what a reply that is NOT the command is worth differs there. Before a
pull request exists the ordinary resume is still in front of the issue, so
prose reaches the developer and the sentence offers it. Past one it does not:
the debt reconciliation that brings a parked issue back to the gate stops the
tick ahead of the stage handler on every poll, so nothing would carry a
human's words to an agent, and a notice promising otherwise would have
somebody writing into a thread nothing reads.
"""
from __future__ import annotations

import logging

from orchestrator import config
from orchestrator.git.measurement import fingerprint as _fingerprint
from orchestrator.workflow.engine import (
    comments as _comments,
    guards as _guards,
)
from orchestrator.workflow.late_split import (
    overrides as _overrides,
    payloads as _payloads,
    state as _late_state,
)
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.implementing import (
    late_command as _command,
    late_records as _records,
    state as _state,
)

log = logging.getLogger("orchestrator.workflow")

# Stamped on the answer one refused command earns, and scoped to the reply it
# was written for. The sentence and the write that consumes that reply cannot
# be made one operation, so a tick that says it and then fails to record it
# reads the same reply again on the next poll -- and the receipt already on the
# thread is what keeps that second reading from saying the same thing twice. An
# HTML comment, so it is invisible in the rendered thread.
_REFUSED_MARKER = (
    "<!--orchestrator-unauthorized-exemption-refused"
    ":issue={issue}:read={read}-->"
)

# What every notice here ends on, worded on the side of publication the park
# was taken on. Before there is a pull request the ordinary resume is still in
# front of this issue, so prose reaches the developer and the sentence says so.
# Past one it is not: the debt reconciliation that brings a parked issue back
# to this gate stops the tick ahead of the stage handler on every poll, so
# nothing on that road would ever carry a human's words to an agent -- and a
# notice promising otherwise would have somebody writing into a thread nothing
# reads.
_HOW_TO_DECIDE = (
    "Post `/orchestrator authorize-oversized {candidate}` as the entire "
    "comment -- the whole comment and the commit spelled in full -- to "
    "publish it as it stands, or reply with the change to make and the "
    "developer is resumed against it."
)

_HOW_TO_DECIDE_PUBLISHED = (
    "Post `/orchestrator authorize-oversized {candidate}` as the entire "
    "comment -- the whole comment and the commit spelled in full -- and it "
    "joins the pull request. That command is the only reply this stage reads "
    "while the park stands: nothing else on the issue runs until the commit "
    "is published, so prose here reaches no agent."
)

_WRONG_CANDIDATE = (
    "{mentions} that command does not name the commit this issue is waiting "
    "on -- an abbreviation is refused too, since nothing here ever writes "
    "one -- so nothing was published and nothing was recorded. The candidate "
    "waiting on a decision is `{candidate}`. "
)

_PARK_NOTICE = (
    "{mentions} this issue's committed implementation adds {additions} lines "
    "against a ceiling of {threshold}, and the record that would let it past "
    "names the commit alone. It was written before an operator's own "
    "authorization was required at publication, so nothing here can show who "
    "agreed that `{candidate}` publishes as one change -- and an adjudicator "
    "answering that it should is exactly what the ceiling is there to catch. "
    "Nothing was pushed, nothing was discarded, and nothing on the record was "
    "removed: the commit is still in the worktree and the adjudication that "
    "accepted it is still recorded. "
)


def _authorizes_the_park(
    gate: _records._Gate, generation: LateGeneration,
) -> bool:
    """Whether a human has told this oversized candidate to publish as it is.

    The one answer an adjudicated candidate with nobody behind it can get, and
    the whole of what a tick does with it. False is held either way -- the
    park taken or re-taken, or a reply answered and consumed -- and True is a
    candidate the caller publishes exactly as it publishes one the reading let
    through.

    Asked here rather than at the gate's door because this is the only owner
    holding a reading: an operator authorizes a change of THIS size against
    THAT ceiling, and the terms of the record are the pair this call froze,
    the additions it counted, and the ceiling it counted them against.
    """
    answer = _command._read_the_park(gate.gh, gate.issue, gate.state)
    if answer is None:
        return not _parked_for_authorization(gate, generation)
    if answer.named != generation.candidate_sha:
        return not _refused(gate, generation, answer)
    return _recorded_authorization(gate, generation, answer)


def _parked_for_authorization(
    gate: _records._Gate, generation: LateGeneration,
) -> bool:
    """Hold an adjudicated candidate nobody has authorized, and say so once.

    The answer an oversized reading gets where an exemption names the commit
    and no authorization does. It is a hold rather than a route because the
    question the adjudication answers has already been answered: the change
    was ruled one change, and sending it back would pay for a second
    adjudicator over that same question and risk a `split` cutting children
    out of work somebody already decided ships whole. What is missing is a
    person, so this asks for one.

    The COUNT is deliberately not made durable, and that is the difference
    between a park and an adjudication. A generation carrying a reading past
    its ceiling is exactly what this workflow means by "an adjudication in
    flight": the dispatcher restores `workflow:decomposing` over one, the
    coordinator owns every later tick of it, and a fresh adjudicator is paid
    for. A candidate waiting on an operator is none of those, so what stays on
    the comment is the pair the freeze already recorded and nothing else --
    the reading is re-taken on the tick that acts, which is the tick whose
    terms an authorization has to be written from anyway.

    Said ONCE per pair. The seams that publish onto a pull request the remote
    already carries re-enter this gate on every poll behind the park, so
    repeating the notice would mention the same people once a poll about a
    decision they have already been asked for. A record already parked for
    this over this candidate is held quietly instead, and that quiet road
    writes nothing at all.

    Nothing is deleted. The exemption, the identity beside it, the approval
    that names the commit a push is owed for, and every other field stay
    exactly as they were found -- the record is what an authorization would be
    checked against, and a park that repaired the pinned comment on the way
    would destroy the evidence it exists to ask about.
    """
    if _stands_over(gate, generation):
        return True
    log.warning(
        "issue=#%d exempts candidate %s on a record no operator "
        "authorization stands behind; holding %d lines against a ceiling of "
        "%d rather than publishing a bypass nobody granted",
        gate.issue.number, generation.candidate_sha,
        generation.additions, generation.threshold,
    )
    _guards._park_awaiting_human(
        gate.gh, gate.issue, gate.state,
        _PARK_NOTICE.format(
            mentions=config.HITL_MENTIONS,
            additions=generation.additions,
            threshold=generation.threshold,
            candidate=generation.candidate_sha,
        ) + _decided_by(gate, generation.candidate_sha),
        reason=_command.PARK_UNAUTHORIZED_EXEMPTION,
    )
    gate.state.set(_state._PARK_REASON, _command.PARK_UNAUTHORIZED_EXEMPTION)
    gate.gh.write_pinned_state(gate.issue, gate.state)
    return True


def _decided_by(gate: _records._Gate, candidate_sha: str) -> str:
    """What every notice here asks for, on the side of publication it is on.

    Both halves say the command and spell it out ready to copy; they differ
    about the OTHER reply, and the difference is what is actually true rather
    than a matter of tone.

    Before there is a pull request the ordinary resume is still in front of
    this issue: a reply that is not the command falls through the park's own
    recovery to the road that feeds guidance to the developer, so the notice
    offers it. Past one it does not. A parked issue on the stages that publish
    onto a pull request the remote already carries reaches this gate through
    the debt reconciliation, which stops the tick ahead of the stage handler
    on every poll -- so nothing there would carry a human's words to an agent,
    and a notice offering it would have somebody writing into a thread nothing
    reads.

    Read off the entry this call was taken on, which is the same fact the
    measurement park's own two wordings are chosen by.
    """
    asked = _HOW_TO_DECIDE if gate.entry is None else _HOW_TO_DECIDE_PUBLISHED
    return asked.format(candidate=candidate_sha)


def _stands_over(
    gate: _records._Gate, generation: LateGeneration,
) -> bool:
    """Whether this park is already up, over this very candidate.

    Both halves are required. The flag and the reason say somebody is waiting
    behind this question rather than behind a timeout, a dirty tree, or a
    reading nobody could take; the recorded candidate says they are waiting
    behind THIS commit. A record naming another one is a park a resumed
    developer's fresh commit has moved past, and the human holding the issue
    has never been told about the candidate now in hand.

    Read off the durable record, which the freeze ahead of this call has
    already written the pair onto -- so what is compared is the commit the
    park is about rather than a count nothing persists.
    """
    if gate.state.get(_state._PARK_REASON) != _command.PARK_UNAUTHORIZED_EXEMPTION:
        return False
    if not gate.state.get(_state._AWAITING_HUMAN):
        return False
    recorded = _late_state.read_late_generation(gate.state)
    return recorded.candidate_sha == generation.candidate_sha


def _recorded_authorization(
    gate: _records._Gate, generation: LateGeneration, answer: _command._Answer,
) -> bool:
    """Record what an operator authorized, take the park off, consume the reply.

    The terms are this gate's OWN reading and nothing the record already
    carried: the pair it froze, the additions it counted, the ceiling they
    were counted against, and the digest recomputed between that pair here --
    so what goes down is a change of this size against this ceiling, which is
    the claim an authorization has to be answerable as.

    A contribution this host cannot fingerprint records nothing and leaves the
    park and the command exactly where they are. Nothing about that is the
    operator's doing, so the next tick takes the same reading again rather
    than asking somebody to authorize the same change twice.

    The record, the park coming down, and the reply being consumed ride one
    write, for the reason every other authorization does: the record without
    the park cleared says a human is owed a question they have answered, the
    park without the record sends the candidate straight back to it, and the
    record without the watermark leaves the same comment able to authorize
    whatever is parked next.
    """
    contribution = _fingerprint._fingerprint_contribution(
        gate.worktree, generation.base_sha, generation.candidate_sha,
    )
    if not contribution.is_fingerprinted:
        log.warning(
            "issue=#%d cannot fingerprint what the authorized candidate %s "
            "contributes (%s); leaving the authorization unread and the "
            "candidate parked",
            gate.issue.number, generation.candidate_sha, contribution.failure,
        )
        return False
    _overrides.record_publication_override(
        gate.state,
        _overrides.LateOversizedPublication(
            candidate_sha=contribution.candidate_sha,
            base_sha=contribution.base_sha,
            fingerprint=contribution.digest,
            additions=generation.additions,
            threshold=generation.threshold,
            comment_id=answer.comment_id,
        ),
    )
    log.info(
        "issue=#%d had its adjudicated candidate %s authorized to publish "
        "unsplit by a trusted operator in comment %d; recording the terms it "
        "was measured on and letting it past the gate",
        gate.issue.number, generation.candidate_sha, answer.comment_id,
    )
    _consumed(gate, answer)
    gate.state.set(_state._AWAITING_HUMAN, False)
    gate.state.set(_state._PARK_REASON, None)
    gate.gh.write_pinned_state(gate.issue, gate.state)
    return True


def _refused(
    gate: _records._Gate, generation: LateGeneration, answer: _command._Answer,
) -> bool:
    """Say why this command changed nothing, and leave the park standing.

    A command naming a commit this issue is not holding is the ordinary way an
    authorization fails: an id copied out of a notice about work a resumed
    developer has since moved past. A bypass may license exactly what a human
    looked at, so it authorizes nothing -- and the human is owed the reason
    and the command that would have worked.

    Consumed on the way out, and that consumption is the point rather than a
    tidiness. The seams that publish onto a pull request the remote already
    carries reach this gate through a debt reconciliation that stops before
    their own handler, so nothing else on those issues ever moves the
    watermark: a reply left unconsumed would stand in every later batch and
    the correct command behind it would never be the last word.

    Consumed past the SENTENCE rather than past the reply, since the sentence
    is posted first and comment ids ascend. Left between the two, the answer
    this tick just wrote is what the next tick's readers find past the
    watermark -- and a resume reads whatever is there as a human's fresh word,
    so the developer would be resumed against the orchestrator's own refusal.

    The sentence and the write that consumes it are two operations, so the
    sentence carries a receipt scoped to the reply it answers and the thread
    is asked for that receipt before it is written a second time -- the same
    at-most-once discipline every other answer in this repository has.
    """
    log.info(
        "issue=#%d was told to authorize %s and is holding %s; answering the "
        "command and leaving the park where it stands",
        gate.issue.number, answer.named, generation.candidate_sha,
    )
    marker = _REFUSED_MARKER.format(
        issue=gate.issue.number, read=answer.comment_id,
    )
    if not _command._already_answered(gate, marker):
        said = _WRONG_CANDIDATE.format(
            mentions=config.HITL_MENTIONS,
            candidate=generation.candidate_sha,
        ) + _decided_by(gate, generation.candidate_sha)
        _comments._post_issue_comment(
            gate.gh, gate.issue, gate.state, f"{said}\n\n{marker}",
        )
    _consumed(gate, answer)
    gate.gh.write_pinned_state(gate.issue, gate.state)
    return True


def _consumed(gate: _records._Gate, answer: _command._Answer) -> None:
    """Record the reply this tick acted on as read, and our own answer with it.

    Staged rather than written, so it lands with whatever else the caller is
    recording or not at all: a watermark moved without the answer beside it
    would drop a command nobody acted on.

    Past the LAST comment on the thread rather than past the reply, and that
    difference is the whole of it where a sentence was posted. Comment ids
    ascend, so an answer of ours lands ABOVE the reply it answers -- and every
    other reader of this thread takes what is past the watermark as a human's
    fresh word. Left at the reply, the refusal this tick just wrote would be
    read on the next poll as guidance nobody wrote and would resume a
    developer against the orchestrator's own sentence. It is the same rule the
    park's own notice rides out on, which is why the park does not have the
    bug and only this road could.

    A thread the client could not read the tip of falls back to the reply,
    which is the answer that is at least never too FAR: a watermark past a
    comment nobody read would drop the very command a later poll is waiting
    for.
    """
    latest = _payloads.as_identity(gate.gh.latest_comment_id(gate.issue))
    gate.state.set(
        _state._LAST_ACTION_COMMENT_ID,
        max(latest or 0, answer.comment_id),
    )
