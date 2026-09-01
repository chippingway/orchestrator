# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The two frozen shapes one run of this page is carried by.

They are held apart because different halves of a run answer them. The page is
the file as it was read -- which file, every run in it, the values a dropdown
may be offered, and how many of those runs are fixtures -- and it is built once,
before a control is drawn. The filters are what those controls then answered,
already normalized to the vocabulary the read model's own filter takes, so the
widget layer and the filter layer never disagree over what "nothing ticked"
means. Neither shape is built here: both are built where the widgets are.

How many runs the file held is a property rather than a stored field, so a page
cannot be constructed claiming a total the runs it carries disagree with.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from orchestrator.observability.trajectory_viewer.filter_models import FilterOptions
from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun


@dataclass(frozen=True)
class _TrajectoryFilters:
    """What the sidebar answered, in the terms the run filter takes."""

    repo: str | None
    backends: Sequence[str] | None
    agent_roles: Sequence[str] | None
    stages: Sequence[str] | None
    issue: int | None
    query: str
    hide_fixtures: bool


@dataclass(frozen=True)
class _TrajectoryPage:
    """One read of the file: where it came from, and what it offers."""

    log_path: Path | None
    runs: Sequence[TrajectoryRun]
    options: FilterOptions
    fixture_total: int

    @property
    def total(self) -> int:
        """Report how many runs the file held, before any narrowing."""
        return len(self.runs)
