# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Whether the human behind an adjudicated commit is one this issue can show.

The size gate lets a handful of commits publish without a reading, and one of
them is the commit an adjudication accepted. That is the exemption, and on its
own it is a claim about a DECISION rather than about a decider: it says this
change was ruled one coherent whole, and nothing in it says who agreed to put
an oversized change on a pull request. An adjudicator is an agent, and an
agent proposing to publish past the ceiling is the thing the ceiling is there
for -- so the exemption is only ever half of a bypass. The other half is an
operator's own authorization, recorded on the `overrides` owner from a comment
somebody wrote at an address anybody can go and read.

This owner is where the two are asked together, and the answer it gives is the
one the gate acts on: a commit both of them name publishes without a reading,
and a commit only the exemption names is measured like any other candidate.
Both halves are held to naming ONE commit, which is the invalidation rule the
exemption already had and the one this adds nothing to -- work committed on
top of an accepted commit is work nobody adjudicated and nobody authorized,
and it is measured as the fresh candidate it is.

The publication DEBT such a commit leaves is the same question one field over,
and it is asked off that debt's own recorded basis rather than inferred from
the records around it. The settlement writes the exemption and the approval in
one breath, so its approval is that adjudication wearing another field; every
other approval is this gate's own answer brought back by a crash, and no human
was ever owed a decision about one. An approval an older binary wrote says
nothing about its grounds, and there the exemption is the only evidence left.

What that leaves is the record an older binary wrote. Before an authorization
was required, a `single` verdict recorded an exemption by itself, so a live
issue can carry an exemption with no gesture behind it. Nothing here deletes
one, migrates one, or reads one as consent. A candidate an unauthorized
exemption names goes to the ordinary cumulative gate, and the reading decides:
at or below the ceiling it publishes exactly as any small candidate does --
the boundary is inclusive, so a change measuring exactly `MAX_ADDED_LINES`
goes out -- and past the ceiling it parks, which `late_consent` beside this
owns along with the command that ends one.

Two things are never held back by any of it. A commit its pull request is
ALREADY standing on publishes: a push of a commit the remote holds moves
nothing, so what is left is the bookkeeping behind it -- the relabel, the
receipt, the debt -- and holding that back would strand a published branch
under a stage nobody is going to advance. And nothing here rewrites work that
is over: a merged or closed issue is finalized before any handler reaches this
gate, so the compatibility is asked at publication time and never as a pass
over records nobody is publishing from.

The rewrite TRANSFER asks this owner's first question before it grants a
permit, since a transfer is the one road past the reading that no record names
in advance: moving an exemption nothing authorizes would hand the rewritten
commit a permission the accepted one never had. What DOES follow the exemption
is the authorization: the write that rotates one carries the other onto the
same pair, so a squash of an authorized candidate stays authorized and a
squash of a legacy one gains nothing it did not have.
"""
from __future__ import annotations

import logging

from orchestrator.git.measurement import fingerprint as _fingerprint
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    formats as _formats,
    overrides as _overrides,
    payloads as _payloads,
)
from orchestrator.workflow.stages.implementing import (
    late_overflow as _overflow,
    late_parks as _parks,
    late_records as _records,
    state as _state,
)

log = logging.getLogger("orchestrator.workflow")

# Why a commit an unauthorized exemption names still publishes, spelled as the
# gate's own log line reads it: the pull request is standing on it already, so
# there is nothing for a push to add and nothing for a hold to hold back.
_ON_ITS_PULL_REQUEST = "is the commit its pull request already stands on"


def _publishes_on_an_exemption(
    gate: _records._Gate, candidate_sha: str,
) -> bool:
    """Whether an adjudication AND an operator both vouch for this commit.

    The claim the gate skips the reading on, and it is deliberately two
    records rather than one. The exemption says the change was ruled one
    coherent whole, which is an agent's answer; the authorization says a human
    who read it agreed to publish past the ceiling, which is the only thing
    that may ever waive a guard against agents publishing past the ceiling.
    Either alone is half a bypass, and half a bypass is measured.

    Both are exact-SHA claims and neither is widened here. A commit made on
    top of an accepted one carries work nobody ruled on and nobody read, so it
    matches neither and is measured as the fresh candidate it is.

    And neither is BELIEVED on its own shape. Every term of an authorization
    but one is the pinned comment agreeing with itself, which a hand edit and
    a half-written crash can both arrange: a group naming this candidate over
    a base nobody froze, with a digest of nothing and a comment id somebody
    typed, reads back whole and licenses an unmeasured push of work no human
    ever saw. The digest is the one term the OBJECTS answer, so it is re-taken
    here between the pair the record names and held to what the record says --
    the same proof the settlement that wrote it took, asked again because this
    call happens on a later poll, on a later process, and on a host that never
    held the content between that pair.

    A reading this host cannot take refuses on the same footing as one that
    disagrees, and what that costs is the measurement the gate would have
    taken anyway.
    """
    if not _exemption.is_exempt(gate.state, candidate_sha):
        return False
    if not _overrides.is_authorized(gate.state, candidate_sha):
        return False
    return _contributes_what_was_authorized(gate)


def _contributes_what_was_authorized(gate: _records._Gate) -> bool:
    """Whether the pair a human authorized still contributes what they read.

    Taken over the pair the RECORD names rather than over anything the
    checkout stands on or a base read now: the worktree is writable for the
    whole of an adjudication and for every tick after it, so its head says
    nothing about what was authorized, and a base read now names a change
    nobody decided about.

    Silent about every way it can fail, because they are one answer. A digest
    that disagrees is a record somebody edited or one taken under rules this
    build reads differently; a reading this host could not take is a store an
    operator repairs rather than a decision anybody made. Neither is grounds
    for a bypass, and both cost the candidate a measurement rather than the
    decision behind it -- the authorization stays exactly where it is, and a
    host that comes back publishes what it says without asking anyone twice.
    """
    authorized = _overrides.read_publication_override(gate.state).publication
    contribution = _fingerprint._fingerprint_contribution(
        gate.worktree, authorized.base_sha, authorized.candidate_sha,
    )
    if contribution.digest == authorized.fingerprint:
        return True
    log.warning(
        "issue=#%d authorizes candidate %s over a contribution this host "
        "does not read back as the one it was authorized on (%s); measuring "
        "it rather than publishing a bypass nothing vouches for",
        gate.issue.number, authorized.candidate_sha,
        contribution.failure or "the digest disagrees",
    )
    return False


def _unauthorized_exemption(
    gate: _records._Gate, candidate_sha: str,
) -> bool:
    """Whether this commit is exempt on a record no human stands behind.

    True for the record an older binary wrote, where a `single` verdict
    recorded an exemption on its own, and true for one whose authorization
    this build cannot read back whole -- a member missing, a field
    hand-edited, a digest taken under a scheme this build does not compute, a
    reading at or under its own ceiling, and a recorded pair that no longer
    contributes the change the digest was taken over. Those are one answer on
    purpose: a bypass nobody can show the terms of is worth exactly what a
    bypass nobody granted is worth, and the cost of both is the measurement
    the gate would have taken anyway.

    False for every candidate no exemption names, which is the ordinary one.
    Nothing here is a claim about a commit this issue never adjudicated.
    """
    if not _exemption.is_exempt(gate.state, candidate_sha):
        return False
    return not _publishes_on_an_exemption(gate, candidate_sha)


def _already_on_its_pull_request(
    gate: _records._Gate, candidate_sha: str, delivered: int,
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

    Two roads reach the same question, because the seams that ask it differ
    in whether a publication was frozen on the way in. A call PAST one hands
    its own frozen entry over and this reads it; the implementing seam freezes
    none -- its push is what opens a pull request -- so `delivered` is the
    proof its caller took for itself, handed in rather than re-taken here so
    one reading answers every road that rests on it. An entry too damaged to
    name a publication is not evidence a pull request stands anywhere and
    answers nothing, rather than falling back to that proof instead.

    What the answer licenses is BOOKKEEPING and never a second publication:
    the number travels out with the verdict, and the seam behind it leases its
    push against this very commit and hands the relabel the pull request the
    proof was about.
    """
    if not _exemption.is_exempt(gate.state, candidate_sha):
        return ""
    if gate.entry is not None:
        return (
            _ON_ITS_PULL_REQUEST
            if gate.entry.is_frozen
            and gate.entry.published_sha == candidate_sha else ""
        )
    return _ON_ITS_PULL_REQUEST if delivered else ""


def _delivered_before_the_relabel(
    gate: _records._Gate, candidate_sha: str,
) -> int:
    """The pull request already standing on this commit, or 0 where none is.

    The window between a push that opened a pull request and a relabel that
    never landed, read from the far end. Nothing froze a publication here, so
    every half of the proof is taken together: the RECEIPT says this stage
    pushed the commit, which is what tells work this issue delivered from a
    tip somebody else moved the branch to; the REMOTE says the pull request is
    standing on it still; and the BRANCH that pull request is open on is the
    one the seam behind this would push.

    Asked of every receipt this seam would answer on, measured or adjudicated
    alike. The note says what this stage last PUSHED and nothing about where
    it went or whether it is still there, so a candidate the gate measured on
    the way out earns exactly the same proof: without it a stale note over a
    pull request that is gone skips the reading, pushes, opens a second pull
    request, and hands the issue on.

    Taken ONCE per gate call and handed to each road that rests on it, rather
    than re-asked: a second reading is a second answer, and the roads it feeds
    have already decided to publish by the time one could disagree.

    Zero for a call that froze a publication, which has its own proof and
    spends no request on this one.

    That last one is what makes "the push moves nothing" true rather than
    merely likely, and it is the whole reason the carve-out is safe. The seam
    resolves its own branch from the record and pushes THAT, then reuses
    whatever open pull request is on it -- so a record naming a pull request
    on some other branch would have this answer license a push to a branch
    nobody has published and a SECOND pull request opened over the same work.
    Verified equal, the push has nothing to send and the lookup behind it
    finds the very pull request this reading proved, which is the difference
    between finishing bookkeeping and publishing again.

    All of it is required and none of it is widened. Without the receipt a
    legacy exemption would publish unmeasured on any head a remote happened to
    agree with; without the remote reading it would publish on a local note
    that is never cleared, over a pull request the branch has since moved off.

    Refused for a pull request this host could not read, one that has merged
    or been closed, one standing on another commit, and one open on another
    branch -- each of which is a publication nothing here can show, so the
    candidate goes to the ordinary cumulative reading and an oversized one
    waits for the authorization it is missing.

    The NUMBER is the answer rather than a bare yes, because the seam behind
    it has two things to pin and nothing else can supply either: the lease,
    which is this commit, and the pull request the bookkeeping belongs to. Fed
    a bare permission it would resolve a branch, take the transport's own
    reading of the remote as its lease, and reuse whatever pull request that
    lookup found -- which is a force-push over a tip that moved since, and a
    second pull request where this one closed since.
    """
    number = _payloads.as_identity(gate.state.get(_state._PR_NUMBER))
    if gate.entry is not None or not number:
        return 0
    if _parks._published_commit(gate.state) != candidate_sha:
        return 0
    reading = _overflow._PublicationReading.taken(gate.gh, number)
    if reading.refusal is not None or reading.state != _overflow._OPEN:
        return 0
    delivered = (
        reading.head_branch == _worktree_paths._resolve_branch_name(
            gate.state, gate.spec, gate.issue.number,
        )
        and _payloads.as_hex(
            reading.head, _formats.COMMIT_LENGTHS,
        ) == candidate_sha
    )
    return number if delivered else 0


def _receipt_answers_alone(
    gate: _records._Gate, candidate_sha: str, delivered: int,
) -> bool:
    """Whether a local receipt may vouch for this commit with nothing beside it.

    The receipt says which commit this stage last PUSHED, and on the initial
    publication it answers on its own: the window it covers is between the
    push that opened a pull request and the relabel that never landed, and no
    publication was frozen there to check it against. That is right for a
    commit this workflow measured on the way out.

    It is NEVER right on its own, whatever the record beside it says. The
    receipt is a local note and it is never cleared, so a branch pushed rounds
    ago carries one still -- and answering on the note alone republishes,
    unmeasured and with no frozen head to lease against, onto a pull request
    that may have moved, merged, closed, or never have been the one this issue
    records. An exemption nothing authorizes makes that worse rather than
    making it so: the work is oversized too.

    So the same proof every commit already delivered is held to is asked here,
    which is the pull request the RECORD names, open, on the branch this seam
    would push, standing on this exact commit. What that costs is the relabel
    finishing a poll later where the remote disagrees -- the candidate goes to
    the ordinary cumulative reading, which parks an oversized one for the
    authorization it is missing and publishes a small one on its own count --
    and the commit stays exactly where it is meanwhile.

    A call that DID freeze a publication is a different question and answers
    True here: the head it froze is checked against the commit by the reader
    behind this, which is the proof this road has to take for itself.
    """
    if gate.entry is not None:
        return True
    return bool(delivered)


def _unauthorized_debt(gate: _records._Gate, candidate_sha: str) -> bool:
    """Whether the push this commit is owed rests on an unauthorized exemption.

    Asked of the approval's own recorded basis rather than of the records
    standing around it, because provenance is a thing only the owner that
    granted an approval knows. The settlement writes the exemption and the
    debt in one breath, so its approval is that adjudication wearing another
    field and is worth exactly what the exemption is worth; every other
    approval on this issue is the gate's own answer brought back by a crash,
    and no human was ever owed a decision about one.

    Inferred from the exemption alone it is wrong in both directions, and both
    are reachable. A candidate the gate measured at or below the ceiling on an
    issue that still carries an older binary's exemption earns a genuine gate
    approval -- refusing it would re-judge a settled reading against a base
    that has moved since, which is the one thing the approval bypass exists to
    prevent. And a settlement's debt whose exemption somebody hand-edited
    would read as the gate's own and publish unmeasured, which is the one
    thing this rule exists to prevent.

    An authorization covering the commit ends the question whichever way the
    basis reads -- and it is the whole authorization that ends it, proved
    against the objects rather than read off the record, since a group naming
    this candidate over terms nobody froze is exactly the hand edit a bypass
    turns on.

    Two bases answer yes, and they are the two an operator's gesture is behind
    -- the settlement's own debt, and the debt a candidate past the ceiling
    earns when a human authorizes it at the gate. The second is the crash
    window this would otherwise leave open: the count behind such an approval
    really was this gate's, so recording it as an ordinary reading would let a
    record damaged between the approval and the push publish an oversized
    change nothing could show the grounds for.

    A record whose basis this build cannot READ is the sharpest of them, and
    it is the one shape a single hand edit reaches: the field the fallback
    turns on, touched, and the approval beside it reads as the gate's own. It
    is refused outright rather than handed to the exemption, because what it
    says is that the record claims grounds and cannot name them -- and grounds
    nobody can show are worth what grounds nobody granted are worth.

    A record with NO basis on it is the opposite record and earns the
    compatibility: an approval an older binary wrote, where the exemption is
    the only evidence there ever was -- so it is read, and read
    conservatively. A commit that exemption names is the adjudication's debt.
    So is a comment that CLAIMS an exemption and cannot say which commit it is
    about: a truncated or hand-edited field is not the same thing as an issue
    that never entered an adjudication, and reading the two alike is how a
    settlement's debt with a damaged exemption beside it publishes unmeasured
    -- the shape a hand edit reaches by touching the one field the bypass
    would otherwise have turned on. An issue carrying no exemption field at
    all is that other thing, and its approval is the gate's own.
    """
    basis = _parks._approved_basis(gate.state)
    if basis:
        return (
            basis in _parks.AUTHORIZED_BASES
            and not _publishes_on_an_exemption(gate, candidate_sha)
        )
    if _parks._unreadable_basis(gate.state):
        return not _publishes_on_an_exemption(gate, candidate_sha)
    if _exemption.is_exempt(gate.state, candidate_sha):
        return not _publishes_on_an_exemption(gate, candidate_sha)
    # Presence and truth asked together, because the answer is the gap between
    # them. `read_exemption` is fail-closed, so a truncated or hand-edited
    # field comes back as no exemption -- right for a caller deciding whether
    # a commit may publish, and wrong for one deciding whose DECISION a debt
    # is. An issue that never entered an adjudication carries no field; one
    # whose field cannot be read carries the claim that an adjudication
    # happened and no way to say which commit it was about.
    if not gate.state.carries(_exemption.LATE_EXEMPT_SHA):
        return False
    return _exemption.read_exemption(gate.state) is None
