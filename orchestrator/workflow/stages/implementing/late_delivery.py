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
"""
from __future__ import annotations

import logging

from orchestrator.git.worktrees import paths as _worktree_paths
from orchestrator.workflow.late_split import (
    formats as _formats,
    payloads as _payloads,
)
from orchestrator.workflow.stages.implementing import (
    late_overflow as _overflow,
    late_parks as _parks,
    late_records as _records,
    state as _state,
)

log = logging.getLogger("orchestrator.workflow")


def _delivered_before_the_relabel(
    gate: _records._Gate, candidate_sha: str,
) -> int:
    """The pull request already standing on this commit, or 0 where none is.

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

    Zero for a call that froze a publication, which has its own proof and
    spends no request on this one. Zero too for a pull request this host could
    not read, one that has merged or been closed, one standing on another
    commit, and one open on another branch -- each of which is a publication
    nothing here can show, so the candidate goes to the reading it would have
    had anyway.
    """
    number = _payloads.as_identity(gate.state.get(_state._PR_NUMBER))
    if gate.entry is not None or not number:
        return 0
    if _parks._published_commit(gate.state) != candidate_sha:
        return 0
    reading = _overflow._PublicationReading.taken(gate.gh, number)
    if reading.refusal is not None or reading.state != _overflow._OPEN:
        return 0
    if not _stands_where_the_push_would_land(gate, reading, candidate_sha):
        return 0
    log.info(
        "issue=#%d records pull request #%d already standing on %s; what is "
        "left for it is the bookkeeping behind a publication that happened",
        gate.issue.number, number, candidate_sha,
    )
    return number


def _stands_where_the_push_would_land(
    gate: _records._Gate,
    reading: _overflow._PublicationReading,
    candidate_sha: str,
) -> bool:
    """Whether this reading is the branch and the tip the seam would publish.

    Both compared against what the SEAM resolves rather than against anything
    the reading supplies for itself, since the question is whether its push
    would move anything: the branch it would push is the one the record names,
    and the commit it would send is the candidate in hand.
    """
    branch = _worktree_paths._resolve_branch_name(
        gate.state, gate.spec, gate.issue.number,
    )
    if reading.head_branch != branch:
        return False
    return _payloads.as_hex(
        reading.head, _formats.COMMIT_LENGTHS,
    ) == candidate_sha


def _receipt_answers_alone(
    gate: _records._Gate, candidate_sha: str, delivered: int,
) -> bool:
    """Whether a local receipt may vouch for this commit with nothing beside it.

    It never may, whatever the record beside it says. The receipt is a local
    note and it is never cleared, so a branch pushed rounds ago carries one
    still -- and answering on the note alone republishes, unmeasured and with
    no frozen head to lease against, onto a pull request that may have moved,
    merged, closed, or never have been the one this issue records.

    So the proof above is asked of every receipt this seam would answer on,
    measured or adjudicated alike. What that costs is the relabel finishing a
    poll later where the remote disagrees -- the candidate goes to the ordinary
    cumulative reading, and the commit stays exactly where it is meanwhile.

    A call that DID freeze a publication is a different question and answers
    True here: the head it froze is checked against the commit by the reader
    behind this, which is the proof that road takes for itself.
    """
    if gate.entry is not None:
        return True
    if delivered:
        return True
    log.info(
        "issue=#%d records a receipt for %s and no open pull request this "
        "host can read as standing on it; measuring the candidate rather "
        "than republishing on a note nothing confirms",
        gate.issue.number, candidate_sha,
    )
    return False
