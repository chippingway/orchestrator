# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The pinned keys the conflict owners key their decisions on.

Every name here is written into the pinned JSON comment live issues already
carry, so renaming one is a migration of every open PR rather than a refactor.
They sit here rather than on whichever owner writes one first because the
writer is never the only reader: `conflict_round` is bumped by five different
exits and read by the cap that ends the loop, and `review_round` is reset by
this stage but consumed by the reviewer rounds `validating` counts after the
handoff.

The settled pair is the same rule one seam further on. A content update the
size gate holds is a round this stage finished and could not publish, and what
names it -- which of the four it was, and the head it produced -- is exactly
what a later tick cannot re-derive: the settlement publishes the commit, so the
resumed tick reads a branch that already carries its base and would call the
round a no-op flip.

One slot, one round. A resume that commits while a receipt is still outstanding
would write its own over it -- pushed, the owed round is cleared without ever
being counted; held, the gate writes over it -- so every road that starts one
yields until the owed round has been counted: the body edit at the door of the
handler, the human reply at the door of the rebase.
"""
from __future__ import annotations

_CONFLICT_ROUND = "conflict_round"

_REVIEW_ROUND = "review_round"

_AWAITING_HUMAN = "awaiting_human"

_PARK_REASON = "park_reason"

# The park reasons this stage records durably, and the ones no human can
# answer. A transient park is a reading that DID NOT HAPPEN -- a ref nothing
# resolved, a status nothing read, a head nothing could name -- so what clears
# it is the same reading taken again, not a reply. The tick that finds one
# standing therefore carries on with its ordinary work rather than waiting.
_REASON_FETCH_FAILED = "fetch_failed"

_REASON_UNREADABLE_DIVERGENCE = "unreadable_divergence"

_REASON_UNREADABLE_HEAD = "unreadable_head"

_REASON_UNREADABLE_WORKTREE = "unreadable_worktree"

_REASON_UNPINNABLE_RECOVERY = "unpinnable_recovery"

_TRANSIENT_PARKS = frozenset((
    _REASON_FETCH_FAILED,
    _REASON_UNREADABLE_DIVERGENCE,
    _REASON_UNREADABLE_HEAD,
    _REASON_UNREADABLE_WORKTREE,
    _REASON_UNPINNABLE_RECOVERY,
))

_SETTLED_OUTCOME = "conflict_settled_outcome"

_SETTLED_SHA = "conflict_settled_sha"
