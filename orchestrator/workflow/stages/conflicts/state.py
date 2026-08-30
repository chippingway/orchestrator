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

The settled pair is the same rule one seam further on. A resolution the size
gate holds is a round this stage finished and could not publish, and what
names it -- which of the two resolutions it was, and the head it produced --
is exactly what a later tick cannot re-derive: the settlement publishes the
commit, so the resumed tick reads a branch that already carries its base and
would call the round a no-op flip.
"""
from __future__ import annotations

_CONFLICT_ROUND = "conflict_round"

_REVIEW_ROUND = "review_round"

_SETTLED_OUTCOME = "conflict_settled_outcome"

_SETTLED_SHA = "conflict_settled_sha"
