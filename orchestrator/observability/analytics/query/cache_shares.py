# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What share of one row's spend was served from cache, per scan target.

Neither the day-bucketed rollup nor the agent-run view stores a cache cost and
a no-cache cost, so the two bands a spend panel stacks are derived rather than
stored: a row's cost is weighted by the cache share of its billable token
volume, and the complement is the no-cache band, which is what makes the two
bands sum back to the total. The split is spelled twice because the two targets
name their columns differently -- a rollup row carries the `total_*` sums of a
day bucket, an agent-run row the per-run counters beneath them -- and declaring
it once per column set is what keeps a stage panel and a review-round panel
from disagreeing about what "cached" is worth.

The Codex counter for the portion of input served from cache -- `cached_tokens`
on a run, `total_cached_tokens` on a bucket -- is already inside the input
total, so it appears in the numerator only: counting it in the denominator as
well would charge the same tokens twice and understate every share. A row that
recorded no tokens at all has no share to compute, so the fraction is pinned to
zero there and its whole cost attributes to no-cache instead of dividing by
zero.
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

AGENT_CACHE_TOKENS_SQL = (
    "(COALESCE(cached_tokens, 0) + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0))"
)
AGENT_ALL_TOKENS_SQL = (
    "(COALESCE(input_tokens, 0) "
    "+ COALESCE(output_tokens, 0) "
    "+ COALESCE(cache_read_tokens, 0) "
    "+ COALESCE(cache_write_tokens, 0))"
)
AGENT_CACHE_FRACTION_SQL = (
    f"CASE WHEN {AGENT_ALL_TOKENS_SQL} = 0 THEN 0 "
    f"ELSE {AGENT_CACHE_TOKENS_SQL}::numeric "
    f"/ {AGENT_ALL_TOKENS_SQL}::numeric END"
)
