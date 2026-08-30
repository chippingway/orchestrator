# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The reviewer round a fix pays for, whether it is pushed or held.

`review_round` is what `MAX_REVIEW_ROUNDS` counts, and every route through the
fix loop advances it on exactly one event: a head the reviewer has not seen
reaching the pull request. Landed, the push is that event. HELD, the gate has
sent the candidate to the adjudication -- the commit is on the branch, a
`single` verdict publishes it from there, and the head the reviewer rejected
is superseded either way -- so the round is spent just the same.

Either form is handed to the gate rather than applied on the way out. The
hold's last act is the relabel, and a caller that counted afterwards would
lose the count to any crash in that window -- nothing goes back for it, since
the settlement publishes the accepted commit itself and the resumed route
finds nothing left to push. A landed push has the same window one step over:
past the write that records it, the approval and the generation are both gone,
so nothing is left on the comment for a later tick to count a round from.

So the value is read ONCE, before the push, and carried from there. The routes
re-apply that same frozen pair once the call returns, which is a no-op where
the gate already wrote it and the count where a push nothing could name never
reached that write. Re-reading the counter instead would count one round
twice.
"""
from __future__ import annotations

from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.stages.implementing import (
    late_records as _late_records,
)
from orchestrator.workflow.stages.validating import state as _state


def _next_review_round(state: PinnedState) -> int:
    """The value this counter takes next, spent by a hold or by a push."""
    return int(state.get(_state._REVIEW_ROUND) or 0) + 1


def _spends_next_round(state: PinnedState) -> _late_records._Spends:
    """The round this route lands on, frozen for the gate to close."""
    return _late_records._Spends(fields=(
        (_state._REVIEW_ROUND, _next_review_round(state)),
    ))


def _bump_review_round(
    state: PinnedState, owed: _late_records._Spends,
) -> None:
    """Count the round a fix that reached the pull request has spent.

    Applied from the pair the caller froze rather than re-read, so a gate that
    already wrote it beside its receipt is agreed with rather than counted
    past.
    """
    _late_records._spend(state, owed)
