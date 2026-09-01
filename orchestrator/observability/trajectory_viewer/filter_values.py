# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one filter value is offered as, narrowed to, and compared against.

The values a page offers are collected off the runs it already read rather than
declared anywhere, so a dropdown only holds a value some run actually carries,
and an empty field is dropped instead of offered as a blank choice that would
select nothing. Each list comes back sorted, because the order a page draws its
options in should not be the order the file happened to be written in.

A caller's own selection is narrowed once per read rather than once per run. A
multi-value choice becomes a set, and an empty one becomes no constraint at
all: "nothing ticked" is how a page spells "everything", so reading it as a
filter would answer an operator who narrowed nothing with an empty table. The
free-text needle is stripped and folded to lower case for the same reason a
whitespace-only one is dropped -- what is left is what a run's text is actually
searched for.

That search reaches every text field a run carries, its steps included, so an
operator looking for a path inside a tool command finds the run that ran it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from orchestrator.observability.trajectory_viewer.filter_models import FilterOptions
from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun


def distinct_sorted(
    runs: Sequence[TrajectoryRun],
    key: Callable[[TrajectoryRun], str],
) -> tuple[str, ...]:
    collected: set[str] = set()
    for run in runs:
        field_value = key(run)
        if field_value:
            collected.add(field_value)
    return tuple(sorted(collected))


def filter_options(runs: Sequence[TrajectoryRun]) -> FilterOptions:
    """Collect distinct, sorted, non-empty filter values."""
    return FilterOptions(
        repos=distinct_sorted(runs, lambda run: run.repo),
        backends=distinct_sorted(runs, lambda run: run.backend),
        agent_roles=distinct_sorted(runs, lambda run: run.agent_role),
        stages=distinct_sorted(runs, lambda run: run.stage),
    )


def matches_query(run: TrajectoryRun, needle: str) -> bool:
    searchable_text: list[str] = [
        run.repo,
        run.stage,
        run.agent_role,
        run.user_input,
        run.system_prompt,
        run.output,
    ]
    searchable_text.extend(run.tools)
    searchable_text.extend(run.skills_triggered)
    searchable_text.extend(run.skills_available)
    for step in run.steps:
        searchable_text.append(step.name)
        searchable_text.append(step.content)
    return any(needle in text.lower() for text in searchable_text if text)


def normalize_filter_values(
    selected_values: Sequence[str] | None,
) -> frozenset[str] | None:
    return frozenset(selected_values) if selected_values else None


def normalize_filter_query(query: str | None) -> str | None:
    if query is None:
        return None
    normalized_query = query.strip().lower()
    return normalized_query or None
