# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One issue's whole life under a small allowance, driven a tick at a time.

The owners under the lifetime ledger are each covered where they live: what
the ledger reads, what the circuit charges, what the park says, what the
command buys. None of those answers the question an operator actually has --
how many agent processes one issue can start before something stops it -- and
none of them could, because the answer is spread over every stage the issue
walks through and every tick it takes to walk it.

So a journey here is a real issue, seeded on a small allowance, run one tick
at a time until the runs run out. Ordinarily a tick is
`_route_issue_to_handler`, and the dispatcher is the entry on purpose: the
hold that stops a spent issue, the sentence it replays, and the command that
buys it more all live there rather than in any handler, and a case that called
the handlers directly would be driving the workflow with the half that ends it
removed. The other tick a leg can name is the base refresh, which runs ahead
of every dispatch rather than through one -- it starts no agent, and what it
does to the counters the caps below are measured on is the reason a journey
built out of it is worth walking.

Nothing carries the count between ticks but the issue's pinned comment. Each
tick builds its own patch set, its own mocks and its own state objects, so
what a later tick knows about an earlier one is exactly what a restarted
process would know -- which is why the totals below are read off the pinned
comment and the spawns are counted per tick and summed.

A leg stages the state a stage would have been entered with rather than
transitioning into it: the label goes on as a hand-applied one, so
`label_history` stays a record of what the WORKFLOW did this walk, and the
staged fields are the ones a stage needs to have work in front of it. What no
leg stages is the park a spent ledger takes -- that is the thing under test,
and it holds the tick from the moment it is written.

Every OTHER cap is pinned wide for the whole walk. Each of them -- the day's
spawn budget, the review-round cap, the conflict-round cap -- refuses a launch
ahead of the ledger and is bounded by a setting the environment can carry, so
a walk run under whatever numbers the suite happens to start with would be
measuring whichever of them ran out first rather than the lifetime total. The
order between them and the ledger is `test_capped_launches.py`'s subject; here
they are held out of the way.
"""
from __future__ import annotations

import contextlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

from orchestrator import config
from orchestrator.git.base_sync import refresh as _base_refresh
from orchestrator.workflow.engine import (
    dispatch as _dispatch,
    run_ledger as _run_ledger,
    run_limit as _run_limit,
)
from tests.support.fakes import FakeComment, FakeGitHubClient, FakeUser, make_issue
from tests.workflow.fixtures import (
    _FAKE_WT,
    _TEST_SPEC,
    KEY_AWAITING_HUMAN,
    KEY_PARK_REASON,
    _agent,
    _issue_branch,
    _open_pr_for,
)

RUN_AGENT = "run_agent"

ISSUE_NUMBER = 1580

PR_NUMBER = 80

BRANCH = _issue_branch(ISSUE_NUMBER)

# Small enough that a whole lifetime fits in a handful of ticks, and large
# enough that the walk before the ceiling is a walk rather than one spawn.
ALLOWANCE = 4

# How many ticks a walk takes past the last run it can pay for. Two rather
# than one: the first meets the refusal that takes the park, and the second is
# the tick that has to add nothing to the thread.
REFUSED_TICKS = 2

DEV_SESSION = "dev-sess"

# What every cap beside the ledger is pinned to for the length of a walk, and
# so also the round count a case about one of those caps has to seed to spend
# it. Wide enough that no journey here reaches it.
HELD_CAP = 100

# The settings pinned to it. Each is a ceiling some road checks ahead of the
# spawn, so any of them left at whatever the environment carries could be the
# thing that ends a walk -- which would make these cases measure a different
# cap on a different host.
_CAPS_HELD_WIDE = (
    "MAX_RETRIES_PER_DAY",
    "MAX_REVIEW_ROUNDS",
    "MAX_CONFLICT_ROUNDS",
)

# The author of every comment a journey's thread carries. The allowlist is
# empty in the suite, so what this login decides is who said something rather
# than whether it was trusted.
OPERATOR = "geserdugarov"


def dispatched_tick(github: FakeGitHubClient, issue) -> Callable[[], Any]:
    """The whole of an ordinary tick: one issue routed by its label."""
    return lambda: _dispatch._route_issue_to_handler(
        github, _TEST_SPEC, issue, github.workflow_label(issue),
    )


def refreshed_tick(github: FakeGitHubClient, issue) -> Callable[[], Any]:
    """The half of a tick that runs before any issue is dispatched.

    The base refresh is not a stage and starts no agent, which is the point of
    driving it here: it rewrites the branch, resets the round the review cap
    is counted on, and hands the issue back to `validating` -- and none of
    that returns a run.
    """
    return lambda: _base_refresh._sync_worktree_with_base(
        github, _TEST_SPEC, _FAKE_WT, issue.number,
    )


@dataclass(frozen=True)
class Leg:
    """One tick of a journey: what it runs, and the world it runs in.

    `staged` is what the workflow would have left on the issue by the time
    this stage is entered, and it is re-applied on every pass so a road that
    consumed its own work -- a batch of feedback marked read, a session
    retired -- has work in front of it again. `world` is the hermetic patch
    context that stage runs inside, and `around` is whatever else has to be
    held open for it (the git seams a rebase reads through).

    `tick` is what the pass actually runs. Ordinarily that is the dispatcher,
    which is the whole of a tick for one issue; a leg that names the base
    refresh instead is the other half of one, and it runs ahead of every
    dispatch rather than through it.
    """

    role: str
    label: str
    staged: Mapping[str, Any]
    world: Mapping[str, Any] = field(default_factory=dict)
    agent_result: Any = field(default_factory=_agent)
    around: Callable[[], Any] | None = None
    tick: Callable[..., Callable[[], Any]] = dispatched_tick
    # What a human says to the issue on the way into this stage, written
    # afresh on every pass. A round that reads a thread consumes it, so a leg
    # whose road is woken by a reply is handed a new one rather than having
    # the mark it just moved put back.
    replies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Journey:
    """One issue walked repeatedly over the same legs until it runs out.

    The legs cycle, so a journey is the shape of a loop an issue really can
    sit in -- a fix answered by a review answered by a fix -- rather than a
    list of stages picked to add up to the allowance.
    """

    name: str
    legs: tuple[Leg, ...]
    seed: Mapping[str, Any] = field(default_factory=dict)
    pull_request: bool = False
    pr_fields: Mapping[str, Any] = field(default_factory=dict)
    # How many ticks the walk takes: enough to spend the whole allowance, and
    # the two that meet the refusal afterwards. A journey carrying a leg that
    # starts no process -- a base refresh -- spends nothing on those passes
    # and says how many more it needs.
    ticks: int = ALLOWANCE + REFUSED_TICKS


@dataclass(frozen=True)
class Pass:
    """What one tick of a walk started, and the round it left behind.

    The round travels with the spawn count because a reset is the one thing a
    journey about resets can only show by watching: a round staged back to
    nothing proves nothing, and a round the tick itself put back proves the
    loop really has no end.
    """

    spawned: int
    review_round: Any


@dataclass(frozen=True)
class Walk:
    """What one walk left behind: the issue, and every pass over it."""

    github: FakeGitHubClient
    issue: Any
    passes: tuple[Pass, ...]

    @property
    def spawns(self) -> tuple[int, ...]:
        """How many processes each tick of this walk started."""
        return tuple(walked.spawned for walked in self.passes)

    @property
    def rounds(self) -> tuple[Any, ...]:
        """The review round each tick left the issue on."""
        return tuple(walked.review_round for walked in self.passes)

    @property
    def total(self) -> int:
        """How many agent processes this walk started, over every tick."""
        return sum(self.spawns)

    @property
    def spent(self) -> int:
        """What the issue's own pinned comment says it has spent."""
        return self.pinned.get(_run_ledger.AGENT_RUNS_USED)

    @property
    def pinned(self) -> dict:
        """The issue's durable state, as any later process would read it."""
        return self.github.pinned_data(self.issue.number)

    @property
    def parked(self) -> bool:
        """Whether the issue is durably stopped on its spent ledger."""
        return bool(self.pinned.get(KEY_AWAITING_HUMAN)) and (
            self.pinned.get(KEY_PARK_REASON) == _run_limit.PARK_AGENT_RUN_LIMIT
        )

    @property
    def notices(self) -> list[str]:
        """Every exhaustion notice this issue's thread was ever told."""
        return [
            body
            for number, body in self.github.posted_comments
            if number == self.issue.number and _EXHAUSTION_PHRASE in body
        ]


# What the park's own sentence says, and nothing else on the thread does.
_EXHAUSTION_PHRASE = "lifetime agent-run allowance"

# The counter a base rebase and a recovered conflict both put back to
# nothing, and the one thing a walk about resets has to be watched for.
_REVIEW_ROUND = "review_round"

# The floor a journey's own comment ids are minted above. The double mints its
# from 1000, so a human's comment written below that would sort under the
# receipts the orchestrator posts in answer to it.
_FIRST_COMMENT_ID = 1000


def seeded(
    journey: Journey,
    *,
    allowance: int | None = ALLOWANCE,
    used: int | None = 0,
    **fields,
) -> tuple[FakeGitHubClient, Any]:
    """One issue at the start of `journey`, on the ledger a case names.

    `used=None` seeds an issue carrying no count of this ledger's own, which
    is every issue that was already running when the ledger arrived.
    `allowance=None` seeds one carrying no ceiling of its own, which is every
    issue nobody has decided anything special about: the setting governs it.
    """
    github = FakeGitHubClient()
    issue = make_issue(ISSUE_NUMBER, label=journey.legs[0].label)
    github.add_issue(issue)
    ledger = {}
    if allowance is not None:
        ledger[_run_ledger.AGENT_RUN_ALLOWANCE] = allowance
    if used is not None:
        ledger[_run_ledger.AGENT_RUNS_USED] = used
    github.seed_state(ISSUE_NUMBER, **{
        **ledger,
        **journey.seed,
        **fields,
    })
    if journey.pull_request:
        _open_pr_for(
            github,
            issue_number=ISSUE_NUMBER,
            pr_number=PR_NUMBER,
            **journey.pr_fields,
        )
    return github, issue


def said(issue, body: str) -> FakeComment:
    """One trusted comment, above every id the thread already carries.

    Above, because a watermark is what decides whether anybody has read it:
    a command written under the id a park's own notice ratcheted the mark to
    is one the tick that answers commands never sees.
    """
    written = FakeComment(
        id=_next_comment_id(issue), body=body, user=FakeUser(OPERATOR),
    )
    issue.comments.append(written)
    return written


def walk(
    case, journey: Journey, ticks: int | None = None, *, seeded_on=None,
) -> Walk:
    """Run `journey`'s issue one tick at a time, and count what it spawned.

    `seeded_on` continues a walk somebody else started, which is how a case
    about what a granted run buys asks its question: the issue is already out
    of runs, and what is under test is what happens after that.

    Each pass records what it started and the review round it left, which is
    what a journey about resets is read against.
    """
    github, issue = seeded_on or seeded(journey)
    with _caps_held_wide():
        passes = tuple(
            _one_pass(case, github, issue, journey.legs[tick % len(journey.legs)])
            for tick in range(_ticks(journey, ticks))
        )
    return Walk(github=github, issue=issue, passes=passes)


@contextlib.contextmanager
def _caps_held_wide():
    """Every cap beside the ledger, pinned wide for the length of a walk."""
    with contextlib.ExitStack() as held:
        for cap in _CAPS_HELD_WIDE:
            held.enter_context(patch.object(config, cap, HELD_CAP))
        yield


def _ticks(journey: Journey, asked: int | None) -> int:
    """How long the walk is: what a case asked for, or what the journey needs."""
    if asked is None:
        return journey.ticks
    return asked


def _one_pass(case, github: FakeGitHubClient, issue, leg: Leg) -> Pass:
    """One pass: what it started, and the review round it left behind."""
    _stage(github, issue, leg)
    return Pass(
        spawned=_ticked(case, github, issue, leg),
        review_round=github.pinned_data(issue.number).get(_REVIEW_ROUND),
    )


def _stage(github: FakeGitHubClient, issue, leg: Leg) -> None:
    """Put the issue in the state its next stage would be entered in."""
    github.apply_foreign_label(issue, leg.label)
    for body in leg.replies:
        said(issue, body)
    state = github.read_pinned_state(issue)
    for key, staged in leg.staged.items():
        state.set(key, staged)
    github.write_pinned_state(issue, state)


def _ticked(case, github: FakeGitHubClient, issue, leg: Leg) -> int:
    """Run one tick of the workflow, and report the processes it started."""
    with contextlib.ExitStack() as stack:
        if leg.around is not None:
            stack.enter_context(leg.around())
        mocks = case._run(
            leg.tick(github, issue),
            run_agent=leg.agent_result,
            **leg.world,
        )
    return mocks[RUN_AGENT].call_count


def _next_comment_id(issue) -> int:
    """One id past everything the thread carries, ours and the humans'."""
    return max(
        (comment.id for comment in issue.comments), default=_FIRST_COMMENT_ID,
    ) + 1
