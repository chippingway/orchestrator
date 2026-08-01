# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which columns the events table promotes out of one JSONL record.

One inventory behind three questions a record is measured against -- what it
must carry, what the table has a column for, and which of those columns hold
JSON. The required-key guard, the promoted-column extraction, and the INSERT's
parameter order all read this list, and a row lands in the wrong column the
moment two of them disagree about it.
"""
from __future__ import annotations


COL_TS = "ts"
COL_REPO = "repo"
COL_ISSUE = "issue"
COL_EVENT = "event"

# Anything outside this list lands in the `extras` JSONB column, so a record
# written by a newer orchestrator version never loses fields to a database
# that has no column for them yet.
PROMOTED_COLUMNS = (
    COL_TS,
    COL_REPO,
    COL_ISSUE,
    COL_EVENT,
    "stage",
    "duration_s",
    "result",
    "agent_role",
    "backend",
    "agent_spec",
    "resume_session_id",
    "session_id",
    "review_round",
    "retry_count",
    "exit_code",
    "timed_out",
    "input_tokens",
    "output_tokens",
    "cached_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "models",
    "turns",
    "cost_usd",
    "cost_source",
)

# psycopg adapts dict / list to JSON natively but a few drivers need an
# explicit Json wrapper, which is what a caller's own `json_adapter` covers.
JSONB_COLUMNS = ("models", "extras")

REQUIRED_KEYS = (COL_TS, COL_REPO, COL_ISSUE, COL_EVENT)
