# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The banner and the five tiles a whole read is summarized in.

What a page draws above its filters: the brand bar naming how many runs the
file holds and how many the current narrowing left, and the KPI strip the
headline counts are rendered into. Both are built off the summary the read
model already totalled rather than off the runs, so the figures an operator
reads are the ones the filters produced.

Every caller-supplied string goes through ``html.escape`` before it reaches the
markup, because a page writes these with ``unsafe_allow_html=True`` and a
repository name, a stage, or a KPI label is record text this viewer does not
own.

The money is formatted here rather than through the shared compact formatters:
those trade digits for a suffix at a fixed threshold, so the total-cost tile
would read ``$12`` where the authoritative figure is ``$12.50``. The same
function renders the four-decimal per-turn estimate the timeline strip carries,
which is why the precision is a keyword rather than two spellings.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from orchestrator.observability.dashboard import formatting
from orchestrator.observability.trajectory_viewer.summaries import TrajectorySummary


# The historical import site the tile shape is published from, so a repr and a
# reader following `__module__` still land where it is documented. The tile
# keeps that site's own spelling for it rather than taking this package's:
# `__module__` and `__qualname__` together are the pair `pickle` resolves a
# class through, so a name the stamped module does not answer to is a load
# error rather than a cosmetic difference.
ORIGIN_MODULE = "orchestrator._trajectory_dashboard_html"


@dataclass(frozen=True)
class _TrajectoryKpi:
    """One headline tile: its label, its figure, and the note under it."""

    label: str
    figure: str
    foot: str = ""


def card_header_html(title: str, sub: str) -> str:
    """Render the title and subtitle line a card opens with."""
    return (
        f'<p class="orch-card-title">{html.escape(title)}</p>'
        f'<p class="orch-card-sub">{html.escape(sub)}</p>'
    )


def topbar_html(total_runs: int, shown_runs: int) -> str:
    """Render the brand bar and the in-view count beside it."""
    return (
        '<div class="orch-topbar"><div class="orch-brand">'
        '<span class="orch-brand-mark">TR</span><div>'
        '<h1>Orchestrator Trajectories</h1>'
        '<p class="orch-sub">agent reasoning traces · '
        f"{formatting.fmt_num(total_runs)} recorded</p></div></div>"
        '<div class="orch-spend"><span class="label">In view</span>'
        f'<span class="value">{formatting.fmt_num(shown_runs)} / '
        f"{formatting.fmt_num(total_runs)}</span></div></div>"
    )


def fmt_cost_usd(amount: float, *, decimals: int = 2) -> str:
    """Render an exact dollar figure with the requested precision."""
    number_format = ",.{0}f".format(decimals)
    return "${0}".format(format(amount, number_format))


def trajectory_kpis(summary: TrajectorySummary) -> tuple[_TrajectoryKpi, ...]:
    """Build the five tiles a summarized read is reported through."""
    if summary.truncated_runs:
        truncated_foot = f"{formatting.fmt_num(summary.truncated_runs)} truncated"
    else:
        truncated_foot = "none truncated"
    return (
        _TrajectoryKpi("Runs", formatting.fmt_num(summary.total_runs), truncated_foot),
        _TrajectoryKpi("Issues", formatting.fmt_num(summary.distinct_issues)),
        _TrajectoryKpi("Repos", formatting.fmt_num(summary.distinct_repos)),
        _TrajectoryKpi("Tool calls", formatting.fmt_num(summary.total_tool_calls)),
        _TrajectoryKpi(
            "Total cost",
            fmt_cost_usd(summary.total_cost_usd),
            "reported + est.",
        ),
    )


def trajectory_kpi_html(kpi: _TrajectoryKpi) -> str:
    """Render one tile, keeping the foot slot even where there is no note."""
    if kpi.foot:
        foot_html = (
            f'<div class="kpi-foot"><span>{html.escape(kpi.foot)}</span></div>'
        )
    else:
        foot_html = '<div class="kpi-foot"></div>'
    return (
        '<div class="orch-kpi"><div class="kpi-top">'
        f'<span class="kpi-label">{html.escape(kpi.label)}</span></div>'
        f'<div class="kpi-value">{html.escape(kpi.figure)}</div>'
        f"{foot_html}</div>"
    )


def kpi_strip_html(summary: TrajectorySummary) -> str:
    """Render the five trajectory KPI tiles."""
    cells = (trajectory_kpi_html(kpi) for kpi in trajectory_kpis(summary))
    return '<div class="orch-kpis">{0}</div>'.format("".join(cells))


_TrajectoryKpi.__module__ = ORIGIN_MODULE
