# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two counter keys the conflict owners key their decisions on.

Both are written into the pinned JSON comment live issues already carry, so
renaming one is a migration of every open PR rather than a refactor. They sit
here rather than on whichever owner writes one first because the writer is
never the only reader: `conflict_round` is bumped by five different exits and
read by the cap that ends the loop, and `review_round` is reset by this stage
but consumed by the reviewer rounds `validating` counts after the handoff.
"""
from __future__ import annotations

_CONFLICT_ROUND = "conflict_round"

_REVIEW_ROUND = "review_round"
