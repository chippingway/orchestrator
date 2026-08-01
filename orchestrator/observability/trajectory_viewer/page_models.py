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

Both report ``orchestrator._trajectory_dashboard_models`` as their module. That
is the import site the page state is published from, so a repr, a pickle, and a
reader following ``__module__`` all still land where it is documented -- and
each keeps that site's own spelling for it, underscore included, because
``__module__`` and ``__qualname__`` together are the pair ``pickle`` resolves a
class through.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from orchestrator.observability.trajectory_viewer.filter_models import FilterOptions
from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun


ORIGIN_MODULE = "orchestrator._trajectory_dashboard_models"


@dataclass(frozen=True)
class _TrajectoryFilters:
    """What the sidebar answered, in the terms the run filter takes."""

    repo: Optional[str]
    backends: Optional[Sequence[str]]
    agent_roles: Optional[Sequence[str]]
    stages: Optional[Sequence[str]]
    issue: Optional[int]
    query: str
    hide_fixtures: bool


@dataclass(frozen=True)
class _TrajectoryPage:
    """One read of the file: where it came from, and what it offers."""

    log_path: Optional[Path]
    runs: Sequence[TrajectoryRun]
    options: FilterOptions
    fixture_total: int

    @property
    def total(self) -> int:
        """Report how many runs the file held, before any narrowing."""
        return len(self.runs)


_TrajectoryFilters.__module__ = ORIGIN_MODULE
_TrajectoryPage.__module__ = ORIGIN_MODULE
