# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Splicing a required condition into a generated clause, and who has no rows.

A query whose table carries a constraint of its own -- `event = 'agent_exit'`,
a repo and issue the drill-down is keyed by -- still has to accept whatever
predicate the filter set generated. The two splices differ only in which side
the required condition lands on, and that side is the binding order: a
`prepend` puts its operand before the generated ones, an `append` after, so a
caller composes the bindings in the same order it composed the clause.

The exclusion probe is the other half of the same contract, for the reads whose
view cannot carry an `event` clause at all.

The finished-run condition is spelled here rather than in each scan that pins
it, because a read narrowing to completed agent runs and a read short
circuiting on the absence of them are two halves of one answer: the literal and
the probe have to name the same event or a cleared multiselect would skip a
scan that would have matched.
"""

from __future__ import annotations

from collections.abc import Sequence

AGENT_EXIT_CONDITION = "event = 'agent_exit'"


def append_where_condition(where: str, condition: str) -> str:
    """Add a required condition after an optional generated predicate."""
    if where:
        return f"{where} AND {condition}"
    return f" WHERE {condition}"


def prepend_where_condition(where: str, condition: str) -> str:
    """Add a required condition before an optional generated predicate."""
    if where:
        return f" WHERE {condition} AND {where.removeprefix(' WHERE ')}"
    return f" WHERE {condition}"


def agent_event_excluded(events: Sequence[str] | None) -> bool:
    """True when the active event filter excludes `agent_exit` rows.

    Functions that query `analytics_agent_runs` cannot push an
    `event IN (...)` clause down into the SQL (the view has no
    `event` column -- it filters internally to `event='agent_exit'`).
    They preserve the dashboard's event-filter contract by calling
    this helper up front and short-circuiting to an empty result:

    - ``None`` -> not excluded (no event filter at all).
    - non-empty sequence that lacks ``"agent_exit"`` -> excluded.
    - empty sequence (the cleared-multiselect signal) -> excluded.

    Keeps the agent-run aggregates in lockstep with `get_summary`
    et al. when the operator clears or narrows the events filter.
    """
    if events is None:
        return False
    if not events:
        return True
    return "agent_exit" not in events
