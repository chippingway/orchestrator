# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Whether the human behind an adjudicated commit is one this issue can show.

The size gate lets a handful of commits publish without a reading, and one of
them is the commit an adjudication accepted. That is the exemption, and on its
own it is a claim about a DECISION rather than about a decider: it says this
change was ruled one coherent whole, and nothing in it says who agreed to put
an oversized change on a pull request. An adjudicator is an agent, and an agent
proposing to publish past the ceiling is the thing the ceiling is there for --
so the exemption is only ever half of a bypass. The other half is an
operator's own authorization, recorded on the `overrides` owner from a comment
somebody wrote at an address anybody can go and read.

This owner is where the two are asked together, and the answer it gives is the
one the gate acts on: a commit both of them name publishes without a reading,
and a commit only the exemption names is measured like any other candidate.
Both halves are held to naming ONE commit, which is the invalidation rule the
exemption already had and the one this adds nothing to -- work committed on
top of an accepted commit is work nobody adjudicated and nobody authorized,
and it is measured as the fresh candidate it is.

What that leaves is the record an older binary wrote. Before an authorization
was required, a `single` verdict recorded an exemption by itself, so a live
issue can carry an exemption with no gesture behind it. Nothing here deletes
one, migrates one, or reads one as consent. A candidate an unauthorized
exemption names goes to the ordinary cumulative gate, and the reading decides:
at or below the ceiling it publishes exactly as any small candidate does --
the boundary is inclusive, so a change measuring exactly `MAX_ADDED_LINES`
goes out -- and past the ceiling it PARKS here, for the one thing that is
actually missing.

Parked rather than routed back into adjudication, and that difference is the
whole of what the compatibility is worth. The change has already been ruled
one change; sending it back would pay for a second adjudicator over a question
somebody answered, and a `split` verdict there would cut children out of work
a human already decided ships whole. What is missing is a person, so the park
asks for one, in the same command the ordinary road asks it in.

Two things are never held back by any of it. A commit its pull request is
ALREADY standing on publishes: a push of a commit the remote holds moves
nothing, so what is left is the bookkeeping behind it -- the relabel, the
receipt, the debt -- and holding that back would strand a published branch
under a stage nobody is going to advance. And nothing here rewrites work that
is over: a merged or closed issue is finalized before any handler reaches this
gate, so the compatibility is asked at publication time and never as a pass
over records nobody is publishing from.

The rewrite TRANSFER beside this is the same allowance one step over, and it
is deliberately left alone. A permit is granted only over an already-published
pull request, a checkout standing on the rewritten commit, and two
contributions that fingerprint to the same digest -- so what it lets past is
the change the remote already carries, wearing a new object id, and no content
nobody read reaches a pull request through it. What DOES follow the exemption
is the authorization: the write that rotates one carries the other onto the
same pair, so a squash of an authorized candidate stays authorized and a
squash of a legacy one gains nothing it did not have.

The park's own answer is read here too, because the park can be taken at
either seam and both have to be able to end it. What ends it is a trusted
whole-comment `/orchestrator authorize-oversized <commit>` naming the parked
candidate, and what it earns is the record the new policy wants: the frozen
pair off the generation this gate itself measured, the additions and the
ceiling that reading took, the digest recomputed between that pair, and the
comment the authorization was made in. The terms are the gate's own reading
rather than anything the record already carried, which is what makes them
answerable -- an operator authorizes a change of THIS size against THAT
ceiling, and the only owner that can say either is the one that counted.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
from orchestrator.git.measurement import fingerprint as _fingerprint
from orchestrator.github.client import GitHubClient
from orchestrator.github.comments import filter_trusted
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import (
    guards as _guards,
    messages as _messages,
)
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    formats as _formats,
    overrides as _overrides,
    payloads as _payloads,
    state as _late_state,
)
from orchestrator.workflow.late_split.models import LateGeneration
from orchestrator.workflow.stages.implementing import (
    late_parks as _parks,
    late_records as _records,
    state as _state,
)

log = logging.getLogger("orchestrator.workflow")

# The park an adjudicated candidate takes when nothing on the record says a
# human agreed to publish it. Its own reason because its recovery is neither a
# session retry nor another reading: what it is waiting for is a person, and
# every tick until one arrives measures the same pair to the same answer.
PARK_UNAUTHORIZED_EXEMPTION = "late_unauthorized_exemption"

# Why a commit an unauthorized exemption names still publishes, spelled as the
# gate's log line reads it: the pull request is standing on it already, so
# there is nothing for a push to add and nothing for a hold to hold back.
_ON_ITS_PULL_REQUEST = "is the commit its pull request already stands on"

_PARK_NOTICE = (
    "{mentions} this issue's committed implementation adds {additions} lines "
    "against a ceiling of {threshold}, and the record that would let it past "
    "names the commit alone. It was written before an operator's own "
    "authorization was required at publication, so nothing here can show who "
    "agreed that `{candidate}` publishes as one change -- and an adjudicator "
    "answering that it should is exactly what the ceiling is there to catch. "
    "Nothing was pushed, nothing was discarded, and nothing on the record was "
    "removed: the commit is still in the worktree and the adjudication that "
    "accepted it is still recorded. Post `/orchestrator authorize-oversized "
    "{candidate}` as the entire comment to publish it as it stands, or reply "
    "with the change to make and the developer is resumed against it."
)


def _publishes_on_an_exemption(
    state: PinnedState, candidate_sha: str,
) -> bool:
    """Whether an adjudication AND an operator both name this commit.

    The claim the gate skips the reading on, and it is deliberately two
    records rather than one. The exemption says the change was ruled one
    coherent whole, which is an agent's answer; the authorization says a human
    who read it agreed to publish past the ceiling, which is the only thing
    that may ever waive a guard against agents publishing past the ceiling.
    Either alone is half a bypass, and half a bypass is measured.

    Both are exact-SHA claims and neither is widened here. A commit made on
    top of an accepted one carries work nobody ruled on and nobody read, so it
    matches neither and is measured as the fresh candidate it is.
    """
    if not _exemption.is_exempt(state, candidate_sha):
        return False
    return _overrides.is_authorized(state, candidate_sha)


def _unauthorized_exemption(state: PinnedState, candidate_sha: str) -> bool:
    """Whether this commit is exempt on a record no human stands behind.

    True for the record an older binary wrote, where a `single` verdict
    recorded an exemption on its own, and true for one whose authorization
    this build cannot read back whole -- a member missing, a field
    hand-edited, a digest taken under a scheme this build does not compute, a
    reading at or under its own ceiling. Those are one answer on purpose: a
    bypass nobody can show the terms of is worth exactly what a bypass nobody
    granted is worth, and the cost of both is the measurement the gate would
    have taken anyway.

    False for every candidate no exemption names, which is the ordinary one.
    Nothing here is a claim about a commit this issue never adjudicated.
    """
    if not _exemption.is_exempt(state, candidate_sha):
        return False
    return not _overrides.is_authorized(state, candidate_sha)


def _already_on_its_pull_request(
    gate: _records._Gate, candidate_sha: str,
) -> str:
    """Why an adjudicated commit publishes untouched, or "" where it may not.

    The one thing an unauthorized exemption still buys, and it buys it from
    the REMOTE rather than from the record: a pull request this call itself
    froze, standing on this exact commit, has already received the work. A
    push of a commit the remote holds moves nothing, so what is being decided
    here is not whether unmeasured bulk may reach a pull request -- it is
    there -- but whether the bookkeeping behind it may finish. Held back, the
    receipt is never written, the debt is never paid, and the relabel never
    lands, which leaves published work under a stage no later tick will
    advance.

    Scoped to a commit an exemption names, and that is not decoration. A tip
    that merely happens to be the candidate in hand says nothing about how it
    got there, while an exemption is this workflow's own record that the
    change was adjudicated -- so what this recognizes is adjudicated work
    already delivered rather than any head a remote happens to agree with.

    Silent for every call taken before anything was published, which is the
    whole implementing seam, and for an entry too damaged to name a
    publication: a group that could not be frozen is not evidence a pull
    request stands anywhere.
    """
    if not _exemption.is_exempt(gate.state, candidate_sha):
        return ""
    entry = gate.entry
    if entry is None or not entry.is_frozen:
        return ""
    if entry.published_sha != candidate_sha:
        return ""
    return _ON_ITS_PULL_REQUEST


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

    The measurement is made durable first, exactly as the routed hold makes
    it: the notice names a size and a ceiling, and the command that answers it
    is recorded against the very pair that was counted, so a tick dying
    between the two has to come back to the reading rather than to a park
    describing numbers nothing kept.

    Said ONCE per pair. The park stands until a human answers it and the same
    reading is re-taken on every poll behind it, so repeating the notice would
    mention the same people once a poll about a decision they have already
    been asked for. A record already parked for this over this candidate is
    held quietly instead; a park over some OTHER candidate is a different
    question and is announced.

    Nothing is deleted. The exemption, the identity beside it, the approval
    that names the commit a push is owed for, and every other field stay
    exactly as they were found -- the record is what an authorization would be
    checked against, and a park that repaired the pinned comment on the way
    would destroy the evidence it exists to ask about.
    """
    told = _stands_over(gate, generation)
    log.warning(
        "issue=#%d exempts candidate %s on a record no operator "
        "authorization stands behind; holding %d lines against a ceiling of "
        "%d rather than publishing a bypass nobody granted",
        gate.issue.number, generation.candidate_sha,
        generation.additions, generation.threshold,
    )
    _parks._persisted(gate, generation)
    if told:
        return True
    _guards._park_awaiting_human(
        gate.gh, gate.issue, gate.state,
        _PARK_NOTICE.format(
            mentions=config.HITL_MENTIONS,
            additions=generation.additions,
            threshold=generation.threshold,
            candidate=generation.candidate_sha,
        ),
        reason=PARK_UNAUTHORIZED_EXEMPTION,
    )
    gate.state.set(_state._PARK_REASON, PARK_UNAUTHORIZED_EXEMPTION)
    gate.gh.write_pinned_state(gate.issue, gate.state)
    return True


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

    Read off the durable record rather than the generation being written, so
    the comparison is what a previous tick left rather than what this one is
    about to leave.
    """
    if gate.state.get(_state._PARK_REASON) != PARK_UNAUTHORIZED_EXEMPTION:
        return False
    if not gate.state.get(_state._AWAITING_HUMAN):
        return False
    recorded = _late_state.read_late_generation(gate.state)
    return recorded.candidate_sha == generation.candidate_sha


def _authorized_by_a_reply(gate: _records._Gate, candidate_sha: str) -> None:
    """Record what an operator wrote on this park, if they wrote it.

    Asked inside the gate rather than at one seam's recovery, because the park
    is taken wherever a candidate is published from and every one of those
    seams has to be able to end it. It costs one local read on every other
    call: a comment with no park of ours on it never reaches the thread.

    The terms are this gate's OWN reading and nothing the record already
    carried. The generation the park persisted names the pair that was
    counted, the additions that reading took, and the ceiling it was counted
    against, and the digest is recomputed between that pair here -- so what
    goes down is a change of this size against this ceiling, which is the
    claim an authorization has to be answerable as. A record whose candidate
    has moved, or that carries no reading at all, authorizes nothing: the park
    below it will be re-taken over whatever is actually in hand.

    A contribution this host cannot fingerprint leaves the park standing and
    the command unconsumed. Nothing about that is the operator's doing, so the
    next tick takes the same reading again rather than asking somebody to
    authorize the same change twice.

    The record, the park coming down, and the reply being consumed ride one
    write, for the reason every other authorization does: the record without
    the park cleared says a human is owed a question they have answered, the
    park without the record sends the candidate straight back to it, and the
    record without the watermark leaves the same comment able to authorize
    whatever is parked next.
    """
    replies = _answers_the_authorization_park(gate.gh, gate.issue, gate.state)
    if not replies:
        return
    recorded = _late_state.read_late_generation(gate.state)
    if not _measured_this_candidate(recorded, candidate_sha):
        return
    if not _unauthorized_exemption(gate.state, candidate_sha):
        return
    contribution = _fingerprint._fingerprint_contribution(
        gate.worktree, recorded.base_sha, recorded.candidate_sha,
    )
    if not contribution.is_fingerprinted:
        log.warning(
            "issue=#%d cannot fingerprint what the authorized candidate %s "
            "contributes (%s); leaving the authorization unread and the "
            "candidate parked",
            gate.issue.number, candidate_sha, contribution.failure,
        )
        return
    _records_the_authorization(gate, recorded, contribution, replies)


def _measured_this_candidate(
    recorded: LateGeneration, candidate_sha: str,
) -> bool:
    """Whether the record carries a reading of the commit in hand.

    What an authorization is written from, so every term of it has to be
    there: the pair the digest is taken between, and a count strictly past the
    ceiling it was counted against. A record naming another candidate belongs
    to a question this commit has moved past, and one whose reading is at or
    under its own ceiling describes a candidate the gate publishes untouched
    -- neither is a bypass anybody had to grant, and the writer below refuses
    both rather than recording an authorization a later reader could not hold
    to anything.
    """
    if recorded.candidate_sha != candidate_sha or not recorded.base_sha:
        return False
    return recorded.is_oversized


def _records_the_authorization(
    gate: _records._Gate,
    recorded: LateGeneration,
    contribution,
    replies: list,
) -> None:
    """Put the authorization down, take the park off, and consume the reply.

    One write, and the order inside it is the order a reader needs: the
    evidence, then the flag that says somebody is still owed a question, then
    the watermark that says which comment was acted on. The comment named is
    the last of the replies this park was answered by -- an operator who wrote
    the command twice made one decision, and the record names the gesture the
    tick actually read.
    """
    comment_id = max(reply.id for reply in replies)
    _overrides.record_publication_override(
        gate.state,
        _overrides.LateOversizedPublication(
            candidate_sha=contribution.candidate_sha,
            base_sha=contribution.base_sha,
            fingerprint=contribution.digest,
            additions=recorded.additions,
            threshold=recorded.threshold,
            comment_id=comment_id,
        ),
    )
    log.info(
        "issue=#%d had its adjudicated candidate %s authorized to publish "
        "unsplit by a trusted operator in comment %d; recording the terms it "
        "was measured on and letting it past the gate",
        gate.issue.number, recorded.candidate_sha, comment_id,
    )
    gate.state.set(_state._AWAITING_HUMAN, False)
    gate.state.set(_state._PARK_REASON, None)
    gate.state.set(_state._LAST_ACTION_COMMENT_ID, comment_id)
    gate.gh.write_pinned_state(gate.issue, gate.state)


def _answers_the_authorization_park(
    gh: GitHubClient, issue: Issue, state: PinnedState,
) -> list:
    """The operator authorizations written on this park, if any.

    Empty for everything else, and each exclusion is its own answer. An issue
    parked for another reason is not this park's to end; a thread with nothing
    new on it is a human who has not replied yet; an outsider's comment is not
    in the reading at all, so nothing they post can authorize anything; and a
    reply carrying real words is guidance, which belongs to the ordinary
    resume that feeds it to the developer rather than to a bypass taken behind
    their back.

    Guidance outranks an authorization in the same batch for the reason it
    does wherever the two meet: they say opposite things -- one that the
    change publishes as it stands, the other that it has to be different --
    and the safe reading of a human who wrote both publishes nothing.

    The command has to name the candidate the park is about. One naming
    another commit is the ordinary way this fails -- an id copied out of a
    notice about work the developer has since been resumed over -- and it is
    left to the ordinary road rather than acted on, since a bypass may license
    exactly what a human looked at.
    """
    if state.get(_state._PARK_REASON) != PARK_UNAUTHORIZED_EXEMPTION:
        return []
    if not state.get(_state._AWAITING_HUMAN):
        return []
    replies = filter_trusted(
        gh.comments_after(issue, state.get(_state._LAST_ACTION_COMMENT_ID)),
    )
    named = _late_state.read_late_generation(state).candidate_sha
    if not replies or not named:
        return []
    if not all(_names(reply) == named for reply in replies):
        return []
    return replies


def _names(reply) -> str:
    """The whole object id one reply authorizes, or "" if it authorizes none.

    A comment that is not the whole command answers "", and so does one whose
    argument is not a whole git object id: nothing here abbreviates, so an
    abbreviation is the mismatch it is rather than a prefix to compare.
    """
    written = _messages._authorized_oversized_candidate(reply)
    if written is None:
        return ""
    return _payloads.as_hex(written, _formats.COMMIT_LENGTHS) or ""
