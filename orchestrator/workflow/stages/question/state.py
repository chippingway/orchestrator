# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The park reasons and pinned-state keys the question owners share.

All of these go into the pinned JSON comment live issues already carry, so
renaming one is a migration rather than a refactor -- and two of them are read
from outside this package as well: `workflow/stages/implementing/` refuses a
`question` -> `implementing` relabel by matching the `question_` prefix, and the
`question_agent` / `question_session_id` pair is what keeps a multi-turn Q&A
locked to the backend that answered its first round.

`_UNSAFE_QUESTION_PARKS` is the set that decides a tick's cleanup policy before
it runs anything: those three are the outcomes where the agent left something on
disk, so the worktree has to survive for an operator to inspect.
"""
from __future__ import annotations

_QUESTION_STAGE = "question"

_QUESTION_AGENT_KEY = "question_agent"

_QUESTION_SESSION_KEY = "question_session_id"

_QUESTION_ANSWER = "question_answer"

_QUESTION_COMMITS = "question_commits"

_QUESTION_DIRTY = "question_dirty"

_QUESTION_SILENT = "question_silent"

_QUESTION_TIMEOUT = "question_timeout"

_UNSAFE_QUESTION_PARKS = frozenset((
    _QUESTION_TIMEOUT, _QUESTION_COMMITS, _QUESTION_DIRTY,
))
