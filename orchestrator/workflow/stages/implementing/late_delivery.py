# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Whether the pull request this issue records is already standing on the commit.

The window between a push that opened a pull request and a relabel that never
landed, read from the far end. `implementing_published_sha` is the note this
stage leaves naming the commit it pushed, and the tick after a crash reads it
to recognize a branch the remote already carries: past the push a pull request
carries the work and only the relabel is owed, so measuring that commit again
and finding it oversized would route a PUBLISHED branch into an adjudication
with nothing left to hold back.

That is what the note is FOR, and it is all the note can say. It records what
this stage last pushed and nothing about where it went or whether it is still
there, and it is never cleared -- so a branch this issue published rounds ago
carries one for the rest of its life. Answered on the note alone, a candidate
skips the reading, is pushed unmeasured and unleased onto a pull request that
may have moved, merged, closed, or never have been the one this issue records,
a SECOND pull request is opened over the same work, and the issue is handed on
as though the whole thing had been published all along.

So the note is proof of nothing by itself, and what makes it proof is asked of
the REMOTE: the pull request the record names, open, standing on this exact
commit, and open on the branch the seam behind the answer would push. Every
one of those is required and none of them is widened. Without the receipt, any
head a remote happened to agree with would do. Without the remote reading, a
local note over a pull request the branch has moved off would do. And without
the branch, a record naming a pull request on some other ref would license a
push to a branch nothing has published.

A call taken PAST a publication asks none of it. That seam freezes an entry of
its own -- the pull request, the stage, and the head it is standing on, each
refused unless it proves itself -- and the entry IS the reading this owner
would take. The implementing seam freezes none, because its push is what opens
a pull request in the first place.

What the answer licenses is BOOKKEEPING and never a second publication, which
is why it is a NUMBER rather than a bare permission. A reading is a moment: the
push behind it is leased against the very commit the proof was about, so a
branch somebody moved in the window rejects it instead of being force-
overwritten, and the relabel is handed that pull request by number, so one
somebody closed in the window holds the tick instead of earning another one
over work the first already carries.

A receipt this build cannot READ at all is the same answer one step earlier.
Every late commit field is read fail-closed, so a hand edit or a half-written
crash comes back as no receipt -- right for a reader asking whether a commit
may publish, and exactly wrong for one asking whether the record is sound. Read
as an absence it publishes, and the push writes a receipt over the damaged
field, destroying what an operator would have repaired it from.

A proof that FAILS is a hold rather than a fall-through, and that is the whole
of what the reading is worth. The commit under it is one this stage's own
record says already went to a remote, so there is no reading of it that makes
republishing safe: measured and found small it would be force-pushed onto a
branch nothing here could confirm and a second pull request opened over it,
which is the exact outcome on every road this proof exists to close. So the
tick parks with the receipt, the pull request number and whatever debt stands
beside them left untouched -- there for the terminal that drains finished work,
and there for the retry once a human has reconciled the record with the remote.

Two candidates are outside that hold and neither is a fall-through: a commit an
adjudication's exemption names, and one an approval already owes a push for.
Each is a DURABLE decision of this workflow's own, carrying its own lease and
its own debt, and holding either over a receipt that cannot be proved would
strand exactly the work those records exist to finish.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from orchestrator import config
from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.workflow.late_split import (
    exemption as _exemption,
    formats as _formats,
    payloads as _payloads,
    state as _late_state,
)
from orchestrator.workflow.stages.implementing import (
    late_overflow as _overflow,
    late_parks as _parks,
    late_records as _records,
    state as _state,
)

log = logging.getLogger("orchestrator.workflow")


# Why the publication a receipt names could not be shown, spelled as the park
# comment reads it. Each is a different thing for an operator to reconcile.
_UNREADABLE_RECEIPT = (
    "the receipt itself is not a whole object id, so it cannot say which "
    "commit this stage published"
)

_NO_PULL_REQUEST = "this issue records no pull request for it to be on"

_UNREADABLE_PULL_REQUEST = (
    "pull request #{number} could not be read from this host"
)

_SETTLED_PULL_REQUEST = (
    "pull request #{number} is {state} rather than open"
)

_FOREIGN_BRANCH = (
    "pull request #{number} is open on `{read}` rather than on `{expected}`, "
    "which is the branch this publication would push"
)

_MOVED_HEAD = (
    "pull request #{number} stands at `{read}` rather than on that commit"
)


# What the unprovable-receipt refusal is logged and reported as.
_UNPROVABLE_RECEIPT = "the publication its own receipt names cannot be shown"


_UNPROVABLE_RECEIPT_PARK = (
    "{mentions} this issue's pinned comment records that this stage has "
    "already pushed, and this tick cannot show the publication that receipt "
    "is about: {refusal}. The candidate in the worktree is `{candidate}`. "
    "That note is never cleared, so measuring "
    "the commit again and publishing it would force-push a branch nothing "
    "here could confirm and open a second pull request over work the first "
    "may already carry. Nothing was pushed and nothing was discarded, and the "
    "receipt, the recorded pull request and whatever push is still owed are "
    "all left exactly as they stand. Reconcile the pinned comment with what "
    "is on the remote, or commit again so the candidate is measured afresh."
)


@dataclass(frozen=True)
class _Delivered:
    """The publication a receipt names, or the reason none could be shown.

    Both together because a caller needs both: the NUMBER is what the
    bookkeeping behind a proved publication is bound to, and the REFUSAL is
    what the park over an unprovable one has to tell a human -- a pull request
    somebody closed, one the branch moved off, and one open on another ref are
    three different things to reconcile.

    Empty on both counts for a call this question is not about at all: one
    that froze a publication of its own, and one whose receipt names some
    other commit.
    """

    number: int = 0
    refusal: str = ""

    @property
    def is_proved(self) -> bool:
        """Whether a pull request was shown standing on the commit."""
        return bool(self.number)


def _delivered_before_the_relabel(
    gate: _records._Gate, candidate_sha: str,
) -> _Delivered:
    """The pull request already standing on this commit, or why none is.

    Nothing froze a publication here, so every half of the proof is taken
    together: the RECEIPT says this stage pushed the commit, which is what
    tells work this issue delivered from a tip somebody else moved the branch
    to; the REMOTE says the pull request is standing on it still; and the
    BRANCH that pull request is open on is the one the seam behind this would
    push.

    That last one is what makes "the push moves nothing" true rather than
    merely likely. The seam resolves its own branch from the record and pushes
    THAT, then reuses whatever open pull request is on it -- so a record naming
    a pull request on some other branch would have this answer license a push
    to a branch nobody has published and a second pull request opened over the
    same work. Verified equal, the push has nothing to send and the lookup
    behind it finds the very pull request this reading proved, which is the
    difference between finishing bookkeeping and publishing again.

    Taken ONCE per gate call and handed to each road that rests on it, rather
    than re-asked: a second reading is a second answer, and the roads it feeds
    have already decided to publish by the time one could disagree. It costs no
    request unless the receipt names the candidate in hand.

    Empty for a call that froze a publication, which has its own proof and
    spends no request on this one, and for a receipt naming some other commit
    -- neither is a question about the candidate in hand.

    A REFUSAL is the answer everywhere else the proof does not hold: a receipt
    this build cannot read at all, no pull request recorded for it to be on,
    one this host could not read, one that has merged or been closed, one
    standing on another commit, and one open on another branch. Each names
    itself, because what the caller does with one is park a human over it and
    they are different things to reconcile.

    The MALFORMED receipt is asked first and apart from the comparison below
    it, because that comparison cannot see it: every late commit field is read
    fail-closed, so a hand edit or a half-written crash comes back as no
    receipt at all -- right for a reader deciding whether a commit may publish,
    and the wrong way round for this one. Read as an absence, the candidate is
    measured and published, the branch force-pushed, a second pull request
    opened over whatever the first may already carry, and the damaged field
    overwritten by the receipt that push writes, which destroys the evidence an
    operator would have repaired it from. It cannot say WHICH commit it named,
    so nothing here can tell whether the candidate in hand is that commit --
    which is the whole reason it refuses rather than comparing.
    """
    number = _payloads.as_identity(gate.state.get(_state._PR_NUMBER))
    if gate.entry is not None:
        return _Delivered()
    if _parks._unreadable_receipt(gate.state):
        return _Delivered(refusal=_UNREADABLE_RECEIPT)
    if _parks._published_commit(gate.state) != candidate_sha:
        return _Delivered()
    if not number:
        return _Delivered(refusal=_NO_PULL_REQUEST)
    return _proved_against(gate, number, candidate_sha)


def _proved_against(
    gate: _records._Gate, number: int, candidate_sha: str,
) -> _Delivered:
    """Hold one numbered pull request to what the push behind it would do.

    Every term is compared against what the SEAM resolves rather than against
    anything the reading supplies for itself, since the question is whether its
    push would move anything: the branch it would push is the one the record
    names, and the commit it would send is the candidate in hand.
    """
    reading = _overflow._PublicationReading.taken(gate.gh, number)
    if reading.refusal is not None:
        return _Delivered(
            refusal=_UNREADABLE_PULL_REQUEST.format(number=number),
        )
    if reading.state != _overflow._OPEN:
        return _Delivered(refusal=_SETTLED_PULL_REQUEST.format(
            number=number, state=reading.state,
        ))
    branch = _worktree_paths._resolve_branch_name(
        gate.state, gate.spec, gate.issue.number,
    )
    if reading.head_branch != branch:
        return _Delivered(refusal=_FOREIGN_BRANCH.format(
            number=number, read=reading.head_branch, expected=branch,
        ))
    observed = _payloads.as_hex(reading.head, _formats.COMMIT_LENGTHS)
    if observed != candidate_sha:
        return _Delivered(refusal=_MOVED_HEAD.format(
            number=number, read=observed or reading.head,
        ))
    log.info(
        "issue=#%d records pull request #%d already standing on %s; what is "
        "left for it is the bookkeeping behind a publication that happened",
        gate.issue.number, number, candidate_sha,
    )
    return _Delivered(number=number)


def _receipt_answers_alone(
    gate: _records._Gate, delivered: _Delivered,
) -> bool:
    """Whether a local receipt may vouch for this commit with nothing beside it.

    It never may, whatever the record beside it says. The receipt is a local
    note and it is never cleared, so a branch pushed rounds ago carries one
    still -- and answering on the note alone republishes, unmeasured and with
    no frozen head to lease against, onto a pull request that may have moved,
    merged, closed, or never have been the one this issue records.

    A call that DID freeze a publication is a different question and answers
    True here: the head it froze is checked against the commit by the reader
    behind this, which is the proof that road takes for itself.
    """
    return gate.entry is not None or delivered.is_proved


def _holds_an_unprovable_receipt(
    gate: _records._Gate, candidate_sha: str, delivered: _Delivered,
) -> bool:
    """Park a candidate whose own receipt names a publication nothing can show.

    Fail-CLOSED, and the alternative is what makes it so. This commit is one
    the record says this stage already pushed, so measuring it is not a
    neutral fallback: a count under the ceiling publishes it, which force-
    pushes a branch nothing here could confirm and opens a second pull request
    over work the first may already carry. There is no reading of an
    unprovable publication that makes republishing onto it safe.

    Parked rather than held silently, because none of the four refusals clears
    itself: a number the record never had, one this host cannot read, a pull
    request somebody settled, and one open somewhere else are each a
    disagreement between the pinned comment and the remote that a person
    resolves. The park writes nothing else -- the receipt, the recorded pull
    request, and any debt beside them stand exactly as they were, for the
    terminal that drains finished work or for the retry behind a repair.

    Two candidates are outside this and neither is a fall-through. A commit an
    adjudication's EXEMPTION names publishes on that verdict, and one an
    APPROVAL owes a push for publishes on that debt and its own recorded
    lease. Both are durable decisions of this workflow's own, taken before any
    receipt was written, and holding either over a note that cannot be proved
    would strand exactly the work those records exist to finish.

    Silent for every candidate no receipt names, which is every ordinary tick,
    and for a call that froze a publication of its own.
    """
    if not delivered.refusal:
        return False
    if _exemption.is_exempt(gate.state, candidate_sha):
        return False
    if _parks._approved_commit(gate.state) == candidate_sha:
        return False
    log.error(
        "issue=#%d records a receipt for %s and cannot show the publication "
        "it names (%s); refusing to measure and republish a commit this "
        "stage has already pushed",
        gate.issue.number, candidate_sha, delivered.refusal,
    )
    return _parks._parked(
        gate,
        _records._reportable(
            gate, _late_state.read_late_generation(gate.state),
        ),
        _UNPROVABLE_RECEIPT,
        _UNPROVABLE_RECEIPT_PARK.format(
            mentions=config.HITL_MENTIONS,
            candidate=candidate_sha,
            refusal=delivered.refusal,
        ),
    )
