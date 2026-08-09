# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The immutable state one render of the analytics page is threaded through.

Streamlit reruns the whole script on every widget interaction, so a render is
one pass with nothing kept between passes. These seven shapes are what that
pass carries from the controls at the top of the page down to the panels at the
bottom, and every one of them is frozen: a section is handed the window, the
filters, and the reads the sections beside it were handed, so a panel narrowing
its own copy would be a page whose chart and whose table report different
windows under one filter line.

``DashboardModules`` is the one shape that is not a reading. Nothing under this
package imports Streamlit or pandas -- they live in the optional ``dashboard``
group -- and the theme is a parameter every panel takes rather than an import,
so a render is handed the caller's own handles instead, and carrying the three
together is what keeps that true through a pipeline several calls deep rather
than re-threading three parameters at each hop.

``DashboardFilters`` is the one with readings derived rather than stored.
``issue`` answers nothing until a repository is picked, because GitHub issue
numbers repeat across repositories: a number typed while every repo is selected
names no single issue, so the drill-down it would open is a trace of unrelated
runs. ``days`` is the half-open window measured in whole days and floored at
one, since it is what per-day rates are divided by and a window opened and
closed on the same date would otherwise divide by zero.

``DashboardControls`` adds what the chrome is drawn into -- the two slots the
topbar and the filter line are written back to once the extent behind them is
known -- and ``DashboardPage`` is the whole opening state: the extent a window
could be picked from at all, those controls, and the plan the load is staged
by. It is built once, before the first read is issued.
``DashboardKpis`` and ``LoadedDashboard`` are what comes back from that load:
the four headline tiles with the two counts the panels below re-report, and
those tiles paired with every read the two waves answered.
``ReliabilityPanelData`` is the one shape assembled for a single panel, because
that panel is the only one drawn from four reads at once and passing them
positionally is how a repo list and a throughput series end up swapped.

The vocabulary these fields are annotated in is imported at runtime rather than
only for a type checker: postponed evaluation leaves an annotation as text, and
``get_type_hints`` resolves that text in the globals of the module the class
names, so a name bound for a checker alone raises for the caller reading it
back.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from orchestrator.observability.analytics.query.overview_models import (
    DataExtent,
    Summary,
)
from orchestrator.observability.dashboard import read_plan, windows


@dataclass(frozen=True)
class DashboardModules:
    st: Any
    pd: Any
    theme: Any


@dataclass(frozen=True)
class DashboardFilters:
    window: windows.DateWindow
    repo: Optional[str]
    issue_input: Optional[int]
    events: Optional[Sequence[str]]
    stages: Optional[Sequence[str]]

    @property
    def issue(self) -> Optional[int]:
        """Report the issue a read may be scoped to, once a repo names one."""
        if self.repo is None:
            return None
        return self.issue_input

    @property
    def days(self) -> int:
        """Report the window's span in whole days, never fewer than one."""
        return max((self.window.end - self.window.start).days, 1)


@dataclass(frozen=True)
class DashboardControls:
    filters: DashboardFilters
    topbar_slot: Any
    meta_slot: Any
    timezone_offset: int


@dataclass(frozen=True)
class DashboardPage:
    extent: DataExtent
    controls: DashboardControls
    reads: read_plan.DashboardReadPlan


@dataclass(frozen=True)
class DashboardKpis:
    tiles: Sequence[dict[str, Any]]
    resolved: int
    rejected: int


@dataclass(frozen=True)
class LoadedDashboard:
    read_results: dict[str, Any]
    kpis: DashboardKpis


@dataclass(frozen=True)
class ReliabilityPanelData:
    repos: Sequence[Any]
    summary: Summary
    throughput: Sequence[Any]
    window: windows.DateWindow
    resolved: int
    rejected: int
