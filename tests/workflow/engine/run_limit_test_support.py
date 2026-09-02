# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Fixtures and protocol values the agent-run-limit park tests read against.

The state a live issue carries is what the park owner is written against, so
these build it directly rather than driving a stage: what the tests pin is the
protocol the dispatcher's hold and every gate that spends a run are written
on, not the road of any one of them.
"""
from __future__ import annotations

from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import run_limit as _run_limit
from orchestrator.workflow.engine.run_ledger import (
    AGENT_RUN_ALLOWANCE,
    AGENT_RUNS_USED,
    AgentRunLedger,
)
from tests.support.fakes import FakeGitHubClient, make_issue
from tests.workflow.fixtures import LABEL_IMPLEMENTING

ISSUE_NUMBER = 1541

ALLOWANCE = 50

RUN_LIMIT_EVENT = "agent_run_limit"

DELIVERED = _run_limit.RunLimitPhase.DELIVERED

RECONCILED = _run_limit.RunLimitPhase.RECONCILED

STANDING = _run_limit.RunLimitPhase.STANDING

GRANTED = _run_limit.RunLimitPhase.GRANTED

REFUSED = _run_limit.RunLimitPhase.REFUSED

WATERMARK = 900

AWAITING_HUMAN = "awaiting_human"

PARK_REASON = "park_reason"

LAST_ACTION_COMMENT_ID = "last_action_comment_id"

NOTICE = _run_limit.AGENT_RUN_LIMIT_NOTICE

ALLOWANCE_FIELD = AGENT_RUN_ALLOWANCE

USED_FIELD = AGENT_RUNS_USED

# The login the fake client posts under, and so the only author a receipt this
# orchestrator reads back off a thread may carry.
BOT_LOGIN = "orchestrator"

OUTSIDER = "stranger"


def ledger(*, allowance: int = ALLOWANCE, used: int | None = None):
    """One spent ledger, as the reader that refuses a spawn hands it over."""
    return AgentRunLedger(
        configured=ALLOWANCE,
        allowance=allowance,
        used=allowance if used is None else used,
        reservation=None,
    )


def state_with(**fields) -> PinnedState:
    return PinnedState(comment_id=1, data=dict(fields))


def parked_state(*, owing: bool = False, **fields) -> PinnedState:
    """An issue standing on an agent-run-limit park, said or still owed.

    Every field is overridable, including the ones that make the park what it
    is: what a hand-edited or older pinned comment leaves behind is exactly
    what the safe defaults are read against.
    """
    standing = {
        AWAITING_HUMAN: True,
        PARK_REASON: _run_limit.PARK_AGENT_RUN_LIMIT,
    }
    parked = state_with(**{**standing, **fields})
    if owing:
        _run_limit._owe_notice(parked, ledger())
    return parked


def notice_text(*, allowance: int = ALLOWANCE, used: int | None = None) -> str:
    return _run_limit._limit_message(ledger(allowance=allowance, used=used))


def issue_and_client(*comments):
    gh = FakeGitHubClient()
    issue = make_issue(ISSUE_NUMBER, label=LABEL_IMPLEMENTING)
    issue.comments.extend(comments)
    gh.add_issue(issue)
    return gh, issue


def owed(state: PinnedState):
    return _run_limit._owed_notice(state)


def phases(gh) -> list:
    return [
        record["phase"]
        for record in gh.recorded_events
        if record["event"] == RUN_LIMIT_EVENT
    ]
