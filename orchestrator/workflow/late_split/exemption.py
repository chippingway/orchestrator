# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The one commit an accepted candidate is let past the size gate on.

A `single` verdict says an oversized candidate is one coherent change after
all, and the whole of what that decision is worth has to outlive the
generation that earned it: the gate re-measures whatever a stage is about to
publish, so a candidate handed back with its generation cleared and nothing
else would be measured past the ceiling again and adjudicated again, forever.
The exemption is what breaks that loop, and it is a commit rather than a flag
for the same reason every other late field is a commit -- a flag would exempt
whatever the worktree ends on next.

So it names exactly the commit that was measured and adjudicated, and nothing
else is exempt. A developer who commits again after the verdict has produced
work nobody adjudicated: the recorded SHA no longer matches, the exemption
does not apply to it, and the gate measures it as a fresh candidate. That is
the invalidation rule in full -- there is no clearing step to remember and no
window in which a stale exemption covers a moved head.

It lives outside `LATE_STATE_KEYS` on purpose, which is the one late field
that does. Clearing late mode is defined as dropping exactly the generation's
own group, and the exemption is the single thing that has to survive that
clear -- it is what the reconciliation writes so the generation can be
cleared at all. Reading and writing it is fail-closed like every other late
field: only a whole git object id is an exemption, so a hand-edited value
never becomes a bypass, and a write that was handed one refuses rather than
recording a field the gate would read.
"""
from __future__ import annotations

from typing import Optional

from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split import formats as _formats
from orchestrator.workflow.late_split import payloads as _payloads

# The commit a decided `single` verdict published under. Spelled here because
# this is the field's owner, and it is deliberately not one of the keys
# `clear_late_generation` drops.
LATE_EXEMPT_SHA = "late_exempt_sha"


def read_exemption(state: PinnedState) -> Optional[str]:
    """Return the commit this issue currently exempts, or None.

    Read through the domain's own object-id reader, so an abbreviation, prose,
    or a value an older binary wrote in some other shape reads back as no
    exemption at all rather than as one nothing can be compared against.
    """
    return _payloads.as_hex(
        state.get(LATE_EXEMPT_SHA), _formats.COMMIT_LENGTHS,
    )


def record_exemption(state: PinnedState, candidate_sha: str) -> None:
    """Exempt exactly this commit from the size gate.

    Refuses anything that is not a whole git object id. The field is read by
    the gate that decides whether a candidate may publish, so a value that
    cannot name one commit is a bypass rather than a record -- and recording
    it here would move the failure onto the reader, which has a candidate in
    hand and nowhere to put it.
    """
    if not _formats.is_hex_of(candidate_sha, _formats.COMMIT_LENGTHS):
        raise _formats.InvalidLateValue(
            f"an exemption is not a commit ({type(candidate_sha).__name__})",
        )
    state.set(LATE_EXEMPT_SHA, candidate_sha)


def clear_exemption(state: PinnedState) -> None:
    """Drop the exemption, leaving every other pinned field alone."""
    state.data.pop(LATE_EXEMPT_SHA, None)


def is_exempt(state: PinnedState, candidate_sha: str) -> bool:
    """Whether THIS commit is the one an adjudication let through.

    Both sides have to be a whole object id and they have to be the same one.
    A candidate the caller could not name, and a recorded exemption that is
    not a commit, each answer False -- the gate's job is to measure what it
    cannot prove was already decided.
    """
    exempt = read_exemption(state)
    if exempt is None:
        return False
    return exempt == _payloads.as_hex(candidate_sha, _formats.COMMIT_LENGTHS)
