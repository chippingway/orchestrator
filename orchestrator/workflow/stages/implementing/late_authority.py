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

from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    overrides as _overrides,
)
from orchestrator.workflow.stages.implementing import (
    late_parks as _parks,
    late_records as _records,
    late_transfer as _transfer,
)

# Why a commit an unauthorized exemption names still publishes, spelled as the
# gate's log line reads it: the pull request is standing on it already, so
# there is nothing for a push to add and nothing for a hold to hold back.
_ON_ITS_PULL_REQUEST = "is the commit its pull request already stands on"


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


def _unauthorized_debt(state: PinnedState, candidate_sha: str) -> bool:
    """Whether the push this commit is owed rests on an unauthorized exemption.

    Asked of the approval's own recorded basis rather than of the records
    standing around it, because provenance is a thing only the owner that
    granted an approval knows. The settlement writes the exemption and the
    debt in one breath, so its approval is that adjudication wearing another
    field and is worth exactly what the exemption is worth; every other
    approval on this issue is the gate's own answer brought back by a crash,
    and no human was ever owed a decision about one.

    Inferred from the exemption alone it is wrong in both directions, and
    both are reachable. A candidate the gate measured at or below the ceiling
    on an issue that still carries an older binary's exemption earns a
    genuine gate approval -- refusing it would re-judge a settled reading
    against a base that has moved since, which is the one thing the approval
    bypass exists to prevent. And a settlement's debt whose exemption
    somebody hand-edited would read as the gate's own and publish unmeasured,
    which is the one thing this rule exists to prevent.

    An authorization covering the commit ends the question ahead of either:
    the debt is authorized whatever granted it.

    Two bases answer yes, and they are the two an operator's gesture is behind
    -- the settlement's own debt, and the debt a candidate past the ceiling
    earns when a human authorizes it here. The second is the crash window this
    would otherwise leave open: the count behind such an approval really was
    this gate's, so recording it as an ordinary reading would let a record
    damaged between the approval and the push publish an oversized change
    nothing could show the grounds for.

    A record with no basis on it is an approval an older binary wrote, and
    there the exemption is the only evidence left -- so it is read, and read
    conservatively. A commit that exemption names is the adjudication's debt.
    So is a comment that CLAIMS an exemption and cannot say which commit it is
    about: a truncated or hand-edited field is not the same thing as an issue
    that never entered an adjudication, and reading the two alike is how a
    settlement's debt with a damaged exemption beside it publishes unmeasured
    -- the shape a hand edit reaches by touching the one field the bypass
    would otherwise have turned on. An issue carrying no exemption field at
    all is that other thing, and its approval is the gate's own.
    """
    if _overrides.is_authorized(state, candidate_sha):
        return False
    basis = _parks._approved_basis(state)
    if basis:
        return basis in _parks.AUTHORIZED_BASES
    if _exemption.is_exempt(state, candidate_sha):
        return True
    return _claims_an_adjudication(state)


def _claims_an_adjudication(state: PinnedState) -> bool:
    """Whether the record says one happened and cannot say what about.

    Presence and truth asked together, because the answer is the gap between
    them. `read_exemption` is fail-closed, so a truncated or hand-edited field
    comes back as no exemption -- right for a caller deciding whether a commit
    may publish, and wrong for one deciding whose DECISION a debt is. An issue
    that never entered an adjudication carries no field; one whose field
    cannot be read carries the claim that an adjudication happened and no way
    to say which commit it was about, which is exactly what a hand edit of the
    one field a bypass turns on produces.
    """
    if not state.carries(_exemption.LATE_EXEMPT_SHA):
        return False
    return _exemption.read_exemption(state) is None


def _approved_on_a_reading(
    gate: _records._Gate, candidate_sha: str,
) -> bool:
    """Whether this commit's debt rests on a decision this gate already made.

    An approval is the gate's own answer brought back by a crash, which is
    what makes skipping the reading for it a repeat rather than a bypass. One
    exception, and it is the only approval that was never a reading at all: a
    commit an approval names because a rewrite TRANSFER let it past. What
    licensed that push is a permit, granted on terms -- a pull request, a
    stage, a record, two fingerprints -- that can each stop being true between
    the grant and the tick that comes back to pay the debt.

    So a debt an OUTSTANDING permission stands beside defers to the permit,
    which `late_transfer` re-asks in full over the record the grant left. That
    is asked of the permission rather than of the commit it names, because the
    two go down in one write for one commit: an approval beside an outstanding
    permission is either the one it licensed or evidence the record disagrees
    with itself, and a hand-edited target would otherwise make the permit
    invisible and leave the approval looking ordinary.

    Refused, the ordinary cumulative gate measures the rewrite like any other
    candidate: an oversized change nothing may publish unmeasured is exactly
    what an unvalidatable permission leaves behind.

    A debt the EXEMPTION left defers on the same footing and for the same
    reason. The settlement writes the approval and the exemption in one
    breath, so an approval naming the exempt commit is that adjudication's own
    publication debt rather than a reading this gate took -- and where nothing
    authorizes the exemption, nothing authorizes the debt either. A gate-owned
    approval, which is every approval for a candidate the reading found at or
    below the ceiling, is untouched by this: it is this gate's own answer
    brought back by a crash, and no human was ever owed a decision about it.
    """
    if _parks._approved_commit(gate.state) != candidate_sha:
        return False
    if _unauthorized_debt(gate.state, candidate_sha):
        return False
    return not _transfer._licensed_by_a_permit(gate.state)
