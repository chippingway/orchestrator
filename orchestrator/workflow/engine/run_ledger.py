# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one issue may spend on agent runs, what it has spent, and on what.

A lifetime total is a different kind of number from the day's spawn budget
beside it. That one is a window: it opens, it fills, and the clock empties it
again, so the fields under it may be dropped and rewritten. This one is spent
once. Nothing returns a run an issue has already taken -- not the next day,
not a park a human answered, not a cancelled cycle, and not an operator moving
the setting -- so the count here is charged upward and never decremented,
never zeroed, and never rolled over. Every one of those would be a way for the
same issue to spend the same ceiling twice.

That is also why the count keeps running while the ceiling is off. An
unlimited setting means nothing turns a run away; it does not mean the runs
stopped happening, and a meter that paused under it would report every issue
that ran while it was off as having spent nothing the moment it came back on.
The setting decides what to DO about the total, so it is read where the total
is judged rather than where it is written.

An issue that predates this ledger has still spent its runs, and they are
recorded -- on the `issue_agent_runs` meter the usage accounting has always
folded onto pinned state. So a count that is missing here starts from that
meter rather than from zero, which is the difference between an in-flight
issue keeping what it has spent and being handed a whole fresh lifetime. The
two meters count the same unit, and this one is the superset of the other:
it charges the launch, so it also holds the runs whose usage never parsed.
The legacy total is therefore a floor as well as a seed, and the count is read
as the larger of the two -- monotonic against both writers rather than against
only its own.

The reservation is what makes the charge safe to take before the spawn. A run
has to be charged BEFORE it is launched -- charged after, it is a run that
crashed, timed out, or was killed mid-flight for free -- and a charge taken
before is a charge that may outlive the launch it was for. So what a launch
holds is written down: `reserved` says the slot is charged and the spawn has
not begun, `started` says the spawn happened. Both are wire strings on live
issues, and the pair is what lets a later tick tell a launch that never ran
from one that did. Nothing settles a reservation by giving the charge back.

Nothing here decides anything and nothing here posts. This owner answers what
an issue is allowed and what it has spent, as one typed snapshot; what to do
about a ledger with nothing left in it belongs to the reader, which owns the
park, the sentence under it, and the write that carries both.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from orchestrator import config
from orchestrator.github.pinned_state import PinnedState

# The ceiling in force on THIS issue, where the issue carries one of its own.
# Absent -- which is every issue nobody has decided anything special about --
# means `MAX_AGENT_RUNS_PER_ISSUE` governs and is read live. Present and
# readable, it governs instead and the setting is not consulted at all: a
# per-issue allowance is a decision somebody took about this issue, and
# re-reading the global where the allowance is spent would make that decision
# worth whatever the global had become since. Recorded as the ceiling itself
# and in the setting's own unit, so a `0` here says unlimited exactly as a `0`
# there does.
AGENT_RUN_ALLOWANCE = "agent_run_allowance"

# How many agent runs this issue has spent in its whole life, across every
# role, every stage, and every cycle it has walked.
AGENT_RUNS_USED = "agent_runs_used"

# The launch currently holding one of those charges, and how far it got.
# Absent means no launch this owner knows about is outstanding.
AGENT_RUN_RESERVATION = "agent_run_reservation"

# What an issue-state projection keeps of this ledger. The allowance and the
# spend are facts about the ISSUE -- what it may have, and what it has already
# taken -- so they outlive any one attempt on it, and a projection that
# dropped them would hand a restarted issue a fresh lifetime. The reservation
# is not one of those facts: it describes a launch, and a projection rebuilds
# an issue that has none.
PROJECTED_KEYS = (AGENT_RUN_ALLOWANCE, AGENT_RUNS_USED)

# The per-issue meter the usage accounting folds every parsed agent exit onto.
# Read here as the seed and the floor of the count above, never written.
_LEGACY_RUNS_USED = "issue_agent_runs"


class RunPhase(StrEnum):
    """How far the launch currently holding a charge has got.

    Two phases rather than one flag, because the window between them is the
    one the charge exists for. A slot charged and not yet spawned and a spawn
    that is actually running cost the issue the same run, but they are not the
    same thing to anybody reading the issue afterwards: only one of them ever
    reached an agent.
    """

    RESERVED = "reserved"
    STARTED = "started"


@dataclass(frozen=True)
class AgentRunLedger:
    """One issue's whole agent-run accounting, as a tick reads it.

    `configured` is what the setting says right now and `allowance` is what
    this issue is actually held to; they differ only where the issue carries
    an allowance of its own. Both are reported because a reader explaining a
    refusal owes a human the number it was made on, and the two answer
    different questions -- what the deployment allows, and what this issue
    was allowed.
    """

    configured: int
    allowance: int
    used: int
    reservation: RunPhase | None

    @property
    def unlimited(self) -> bool:
        """Whether the allowance in force bounds nothing at all."""
        return self.allowance <= 0

    @property
    def remaining(self) -> int | None:
        """How many runs are left under the allowance, if it bounds any.

        None where the allowance is unlimited: there is no number of runs left
        under a ceiling there is none of, and answering with one would be a
        remaining count a reader could compare against zero and refuse on.

        Floored at zero rather than reported negative. A count past the
        allowance is an ordinary reading -- an issue that spent runs under a
        wider ceiling, or under none -- and what it has left is nothing.
        """
        if self.unlimited:
            return None
        return max(self.allowance - self.used, 0)


def _read_ledger(state: PinnedState) -> AgentRunLedger:
    """This issue's allowance, what it has spent, and the launch in flight."""
    return AgentRunLedger(
        configured=config.MAX_AGENT_RUNS_PER_ISSUE,
        allowance=_allowance_in_force(state),
        used=_runs_used(state),
        reservation=_reservation(state),
    )


def _reserve_run(state: PinnedState) -> AgentRunLedger:
    """Charge one run to this issue and record the launch it was charged for.

    In memory only, like every other field a tick stages: what makes the
    charge durable is the caller's own write, which keeps the count and the
    launch it was taken for in one write rather than two.

    The charge lands ahead of the spawn on purpose. Charged behind it, a run
    that crashed, timed out, or was killed mid-flight is a run the issue spent
    and the ledger never saw -- and those are exactly the runs a lifetime
    ceiling exists to stop an issue repeating.
    """
    state.set(AGENT_RUNS_USED, _runs_used(state) + 1)
    state.set(AGENT_RUN_RESERVATION, RunPhase.RESERVED)
    return _read_ledger(state)


def _start_reserved_run(state: PinnedState) -> bool:
    """Move a standing reservation to the phase a launch that ran is in.

    Returns whether there was one to move. An issue holding no reservation is
    not given one here: the charge is what a reservation stands for, and one
    minted at the spawn would be a launch nothing paid for.
    """
    if _reservation(state) is None:
        return False
    state.set(AGENT_RUN_RESERVATION, RunPhase.STARTED)
    return True


def _settle_run(state: PinnedState) -> None:
    """Drop the reservation a finished launch held.

    The charge is untouched, which is the whole point of settling rather than
    releasing: the run happened, the issue paid for it, and what ends is only
    the claim that a launch is outstanding.
    """
    state.data.pop(AGENT_RUN_RESERVATION, None)


def _allowance_in_force(state: PinnedState) -> int:
    """The ceiling this issue is actually held to.

    The issue's own where it carries a readable one, and the configured
    setting everywhere else. A field that is not a real, non-negative whole
    number is not an allowance somebody decided -- a hand edit, an older
    binary, a truncated write -- and reading it as one would hold the issue to
    a number nothing wrote. Falling back to the setting is the ordinary answer
    every issue without a per-issue allowance already gets.
    """
    allowance = _counted(state.get(AGENT_RUN_ALLOWANCE))
    if allowance is None:
        return config.MAX_AGENT_RUNS_PER_ISSUE
    return allowance


def _runs_used(state: PinnedState) -> int:
    """How many agent runs this issue has spent, over both meters.

    The larger of the two rather than this ledger's own. An issue that
    predates the ledger has spent runs only the legacy meter recorded, and one
    running under both is counted by both -- so the larger is the count that
    loses neither, and it can only ever go up.

    A field that is not a real, non-negative whole number counts as nothing
    rather than raising: a damaged meter must not strand an issue behind a
    crash on every poll, and the other meter is still there to answer.
    """
    meters = (
        _counted(state.get(AGENT_RUNS_USED)),
        _counted(state.get(_LEGACY_RUNS_USED)),
    )
    return max(
        (count for count in meters if count is not None), default=0,
    )


def _reservation(state: PinnedState) -> RunPhase | None:
    """The launch this issue has outstanding, if it names a known phase.

    Anything else -- absent, hand-edited, or a phase written by a binary this
    one is older than -- reads as no reservation at all. What that costs is a
    launch nobody can account for; what reading an unknown phase as a live one
    would cost is a reader acting on a claim it cannot interpret.
    """
    try:
        return RunPhase(state.get(AGENT_RUN_RESERVATION))
    except ValueError:
        return None


def _counted(raw: Any) -> int | None:
    """One counted field, or None unless it is a real whole count.

    Zero is a real answer for both fields this reads -- an unlimited
    allowance, and an issue that has spent nothing -- so absence is reported
    as None rather than as zero, leaving each caller to say what its own
    missing field means. `bool` is refused explicitly, since it is an `int` in
    this language and a `true` would otherwise count as one run.
    """
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return None
    return raw
