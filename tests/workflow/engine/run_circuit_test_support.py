# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Fixtures for driving one launch through the agent-run circuit.

Every case here goes through `_run_agent_tracked`, because the boundary is
what the circuit is written against: what a test has to be able to see is
whether a process was invoked, what the issue durably said at the moment it
was, and what the caller was left holding afterwards.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

from orchestrator import config
from orchestrator.agents import AgentResult, runner as _agent_runner
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import (
    run_circuit as _run_circuit,
    run_limit as _run_limit,
    usage as _usage,
)
from tests.support.fakes import FakeGitHubClient, FakeIssue, make_issue
from tests.workflow.fixtures import LABEL_IMPLEMENTING

ISSUE_NUMBER = 1543

# Narrow enough that a case can spend it in one line, and wide enough that an
# ordinary launch has room under it.
ALLOWANCE = 3

ROLE = "developer"

STAGE = "implementing"

BACKEND = "codex"

PROMPT = "implement the widget"

WORKTREE = Path("/tmp/fake-worktree")

USED = "agent_runs_used"

RESERVATION = "agent_run_reservation"

FINGERPRINT = "agent_run_fingerprint"

AWAITING_HUMAN = "awaiting_human"

PARK_REASON = "park_reason"

RESERVED = "reserved"

STARTED = "started"

RUN_LIMIT_EVENT = "agent_run_limit"

PARK_AGENT_RUN_LIMIT = _run_limit.PARK_AGENT_RUN_LIMIT

EVENT_AGENT_SPAWN = "agent_spawn"

EVENT_AGENT_EXIT = "agent_exit"

# What a process the shutdown sweep killed reports, and what a launch that
# never became a process reports instead -- there was no exit to take one from.
INTERRUPTED_EXIT_CODE = -15

NO_PROCESS_EXIT_CODE = -1

# A launch this issue never made, so a charge recorded under it is one the
# request under test may not claim.
OTHER_LAUNCH = "0f0f0f0f"

_WRITE_REFUSED = "pinned write refused"

_READ_REFUSED = "pinned read refused"


def agent_result(**overrides) -> AgentResult:
    """What the runner hands back when a process actually ran."""
    finished = {
        "session_id": "sess-circuit",
        "last_message": "done",
        "exit_code": 0,
        "timed_out": False,
        "stdout": "",
        "stderr": "",
    }
    return AgentResult(**{**finished, **overrides})


def fingerprint(**overrides) -> str:
    """The launch identity the default request below is charged under."""
    named = {
        "agent_role": ROLE,
        "stage": STAGE,
        "backend": BACKEND,
        "prompt": PROMPT,
        "cwd": WORKTREE,
    }
    return _usage._AgentRunRequest(**{**named, **overrides}).fingerprint


class CircuitGitHubClient(FakeGitHubClient):
    """A client that remembers its pinned writes and can refuse them.

    The refusals are what the circuit's own promises are read against: a
    launch may not reach a process on a state nobody could read or a charge
    nobody could record, and neither failure is one a stage above could see
    from the result alone.
    """

    def __init__(self, **client_fields) -> None:
        super().__init__(**client_fields)
        self.writes: list[dict] = []
        self.unreadable = False
        self.unparsed = False
        self._writes_allowed: int | None = None

    def refuse_write(self, *, after: int = 0) -> None:
        """Refuse the pinned write that follows `after` further ones."""
        self._writes_allowed = after

    def read_pinned_state(self, issue: FakeIssue) -> PinnedState:
        if self.unreadable:
            raise RuntimeError(_READ_REFUSED)
        if self.unparsed:
            return PinnedState(comment_id=1, data={}, parsed=False)
        return super().read_pinned_state(issue)

    def write_pinned_state(
        self, issue: FakeIssue, state: PinnedState,
    ) -> PinnedState:
        self.writes.append(dict(state.data))
        if self._writes_allowed is not None:
            if self._writes_allowed <= 0:
                raise RuntimeError(_WRITE_REFUSED)
            self._writes_allowed -= 1
        return super().write_pinned_state(issue, state)


@dataclass
class Launch:
    """One tracked run driven through the circuit, and what it left.

    `observed` is the durable pinned payload as it stood each time a process
    was invoked, so a case can ask both whether the run happened and what the
    issue had already recorded when it did.
    """

    gh: CircuitGitHubClient
    issue: FakeIssue
    state: PinnedState
    answer: AgentResult | None = None
    observed: list[dict] = field(default_factory=list)

    @property
    def invocations(self) -> int:
        return len(self.observed)

    @property
    def durable(self) -> dict:
        return self.gh.pinned_data(self.issue.number)

    @property
    def spent(self) -> int:
        """How many runs the issue durably records having taken."""
        return self.durable.get(USED, 0)

    @property
    def phases(self) -> list:
        return [write.get(RESERVATION) for write in self.gh.writes]

    def events(self, name: str) -> list[dict]:
        return [
            record for record in self.gh.recorded_events
            if record["event"] == name
        ]


@dataclass
class _Invocation:
    """The runner seam a case drives, and what it records on the way through.

    A class rather than a closure so the durable read happens at the moment a
    process would have started: what a launch has already paid is only worth
    asserting from inside the call it paid for.
    """

    launch: Launch
    outcome: AgentResult | Exception | None = None

    def __call__(self, *spawn_args, **spawn_fields) -> AgentResult:
        self.launch.observed.append(self.launch.durable)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return agent_result() if self.outcome is None else self.outcome


def seeded(gh: CircuitGitHubClient | None = None, **pinned) -> Launch:
    """One issue whose pinned comment already says `pinned`.

    The caller's own state is read back off the issue, the way a tick's is,
    so a case that stages a field onto it is staging it over durable state
    rather than over nothing.
    """
    client = gh or CircuitGitHubClient()
    issue = make_issue(ISSUE_NUMBER, label=LABEL_IMPLEMENTING)
    client.add_issue(issue)
    client.write_pinned_state(issue, PinnedState(data=dict(pinned)))
    client.writes.clear()
    return Launch(gh=client, issue=issue, state=client.read_pinned_state(issue))


def run_launch(
    launch: Launch,
    *,
    outcome: AgentResult | Exception | None = None,
    allowance: int = ALLOWANCE,
    **request_fields,
) -> Launch:
    """Drive one tracked run, recording what the process saw."""
    named = {
        "agent_role": ROLE,
        "stage": STAGE,
        "backend": BACKEND,
        "prompt": PROMPT,
        "cwd": WORKTREE,
    }
    budget = _run_circuit.AgentRunBudget(
        issue=launch.issue, state=launch.state,
    )
    with patch.object(config, "MAX_AGENT_RUNS_PER_ISSUE", allowance), \
            patch.object(
                _agent_runner,
                "run_agent",
                side_effect=_Invocation(launch, outcome),
            ):
        launch.answer = _usage._run_agent_tracked(
            launch.gh, budget, **{**named, **request_fields},
        )
    return launch
