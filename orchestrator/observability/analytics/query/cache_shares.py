# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What share of one rollup row's spend was served from cache.

The rollup stores a single `total_cost_usd` per bucket, so the cache and
no-cache bands a cost panel stacks are derived rather than stored: a row's cost
is weighted by the cache share of its billable token volume, and the complement
is the no-cache band, which is what makes the two bands sum back to the total.

`total_cached_tokens` is the Codex counter for the portion of input served from
cache and is already inside `total_input_tokens`, so it appears in the
numerator only -- counting it in the denominator as well would charge the same
tokens twice and understate every share. A bucket that recorded no tokens at
all has no share to compute, so the fraction is pinned to zero there and its
whole cost attributes to no-cache instead of dividing by zero.
"""

from __future__ import annotations

ROLLUP_CACHE_TOKENS_SQL = (
    "(COALESCE(total_cached_tokens, 0) + COALESCE(total_cache_read_tokens, 0) + COALESCE(total_cache_write_tokens, 0))"
)
ROLLUP_ALL_TOKENS_SQL = (
    "(COALESCE(total_input_tokens, 0) "
    "+ COALESCE(total_output_tokens, 0) "
    "+ COALESCE(total_cache_read_tokens, 0) "
    "+ COALESCE(total_cache_write_tokens, 0))"
)
ROLLUP_CACHE_FRACTION_SQL = (
    f"CASE WHEN {ROLLUP_ALL_TOKENS_SQL} = 0 THEN 0 "
    f"ELSE {ROLLUP_CACHE_TOKENS_SQL}::numeric "
    f"/ {ROLLUP_ALL_TOKENS_SQL}::numeric END"
)
