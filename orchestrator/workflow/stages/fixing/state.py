# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The pinned-state keys the fixing owners key their decisions on.

Every one of these is written into the pinned JSON comment live issues already
carry, so renaming one is a migration of every open PR rather than a refactor.

They sit here rather than on whichever owner happens to write one first because
the writer is rarely the reader. `pending_fix_at` is the sharpest case: the
in_review route sets it and this stage never does, yet it is the discriminator
`parked` reads to decide whether a transient park may recover itself and
`resume` reads to decide whether a pushed fix resets `review_round` or bumps
it. `park_reason` is the same shape from the other direction -- the base-sync
retry loop writes reasons this stage must recognize and refuse to answer.
"""
from __future__ import annotations

_AWAITING_HUMAN = "awaiting_human"

_PENDING_FIX_AT = "pending_fix_at"

_PARK_REASON = "park_reason"

_REVIEW_ROUND = "review_round"

_CONFLICT_ROUND = "conflict_round"
