# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The headline counts a filtered run set is read back as.

Every tile the page's KPI strip carries is totalled here, and off the runs that
survived filtering rather than off the file, so what an operator reads is the
window they narrowed to. Two of the counts are distinct rather than summed: an
issue is one issue however many runs it took, and a repository is counted only
where a run named one, because a record written without one is not a repository
of its own. The money is the same care in the other direction -- a run with no
usage summary and a run whose cost was never priced each contribute nothing,
instead of a zero that would read as free work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun


@dataclass(frozen=True)
class TrajectorySummary:
    """Headline counts for the filtered run set."""

    total_runs: int = 0
    distinct_issues: int = 0
    distinct_repos: int = 0
    total_tool_calls: int = 0
    truncated_runs: int = 0
    total_cost_usd: float = field(default_factory=float)


def summarize(runs: Sequence[TrajectoryRun]) -> TrajectorySummary:
    """Build headline counts for a filtered run set."""
    return TrajectorySummary(
        total_runs=len(runs),
        distinct_issues=len({(run.repo, run.issue) for run in runs}),
        distinct_repos=len({run.repo for run in runs if run.repo}),
        total_tool_calls=sum(run.tool_calls for run in runs),
        truncated_runs=sum(1 for run in runs if run.truncated),
        total_cost_usd=sum(run.cost_usd for run in runs if run.cost_usd is not None),
    )
