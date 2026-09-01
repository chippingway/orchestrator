# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a run cost, tallied once for the whole run and once per turn.

Two readings of the same spend, and the note between them is why there are two.
The run-level row is the figure the provider reported for the whole run, which
is the authoritative one; the strip drawn at an assistant-turn boundary is a
claude-only estimate this orchestrator priced itself. The two need not sum, so
the row says so in the copy rather than leaving an operator to reconcile them
-- and it says it differently for a backend that recorded no turns at all,
where there are no strips to reconcile against and the run summary is the only
usage surface the page has.

A chip is drawn for a fact the record actually carried. The cached-token chip
is dropped where a backend reports none rather than always reading zero, and
the cache-hit pill is drawn only where a turn read from cache. The cost chip is
the exception: it names its source whether or not a figure resolved, so a run
the pricing tables could not resolve reads as its source alone rather than as
free work.

Money is the exact-cents formatter the KPI strip is rendered with, asked for
four decimals on a turn: a per-turn estimate is routinely sub-cent, and two
decimals would floor a real charge to ``$0.00``.

Every caller-supplied string goes through ``html.escape`` before it reaches the
markup, because a page writes these with ``unsafe_allow_html=True`` and a model
name and a cost source are both record text this viewer does not own.
"""

from __future__ import annotations

import html

from orchestrator.observability.dashboard import formatting
from orchestrator.observability.trajectory_viewer.models import TurnUsageView
from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun
from orchestrator.observability.trajectory_viewer.summary_html import fmt_cost_usd


USAGE_SEPARATOR = '<span class="orch-traj-usage-sep">·</span>'


def usage_chip(text: str, css_class: str = "") -> str:
    """Render one pill, carrying the extra class where the caller named one."""
    classes = f"orch-traj-chip {css_class}".rstrip()
    return f'<span class="{classes}">{html.escape(text)}</span>'


def run_usage_chips(run: TrajectoryRun) -> list[str]:
    """Build the pills a run's own usage summary is read as."""
    usage = run.run_usage
    if usage is None:
        return []
    chips = [usage_chip(model) for model in usage.models]
    chips.extend(
        (
            usage_chip(f"total {formatting.fmt_num(usage.total_tokens)} tok"),
            usage_chip(f"in {formatting.fmt_num(usage.input_tokens)}"),
            usage_chip(f"out {formatting.fmt_num(usage.output_tokens)}"),
            usage_chip(f"cache-read {formatting.fmt_num(usage.cache_read_tokens)}"),
            usage_chip(f"cache-write {formatting.fmt_num(usage.cache_write_tokens)}"),
        )
    )
    if usage.cached_tokens:
        chips.append(usage_chip(f"cached {formatting.fmt_num(usage.cached_tokens)}"))
    if usage.turns is not None:
        chips.append(usage_chip(f"{usage.turns} turns"))
    source = run.cost_source or "unknown"
    cost_label = (
        source
        if run.cost_usd is None
        else f"{source} {fmt_cost_usd(run.cost_usd)}"
    )
    chips.append(usage_chip(cost_label, "cost"))
    return chips


def run_usage_note(run: TrajectoryRun) -> str:
    """Say how the row below relates to the strips, for this backend."""
    if run.turns:
        return (
            "Run cost is authoritative when reported. The per-turn strips in "
            "the timeline are claude-only estimates and need not sum to it; "
            "entries with no strip (tool results, user turns) are turn inputs, "
            "billed on the next assistant turn."
        )
    return (
        "Run cost is authoritative when reported. Per-turn usage is not "
        "available for this backend, so the run-level summary is its only "
        "usage surface."
    )


def run_usage_html(run: TrajectoryRun) -> str:
    """Render run-level usage chips and their accuracy note."""
    if run.run_usage is None:
        return ""
    chips_html = "".join(run_usage_chips(run))
    row_html = (
        '<div class="orch-traj-chips"><span class="lbl">Run usage</span>'
        f"{chips_html}</div>"
    )
    return (
        f'{row_html}<p class="orch-traj-usage-note">'
        f"{html.escape(run_usage_note(run))}</p>"
    )


def turn_usage_html(usage: TurnUsageView) -> str:
    """Render compact usage for one assistant turn."""
    segments = []
    if usage.model:
        segments.append(
            f'<span class="orch-traj-turn-model">{html.escape(usage.model)}</span>',
        )
    estimated_cost = (
        "est. n/a"
        if usage.cost_usd is None
        else f"est. {fmt_cost_usd(usage.cost_usd, decimals=4)}"
    )
    usage_labels = (
        f"in {formatting.fmt_num(usage.input_tokens)} tok",
        f"out {formatting.fmt_num(usage.output_tokens)} tok",
        f"cache-read {formatting.fmt_num(usage.cache_read_tokens)}",
        f"cache-write {formatting.fmt_num(usage.cache_write_tokens)}",
        estimated_cost,
    )
    segments.extend(f"<span>{usage_label}</span>" for usage_label in usage_labels)
    cache_hit = (
        '<span class="orch-traj-cache-hit">cache hit</span>'
        if usage.cache_read_tokens > 0
        else ""
    )
    return (
        '<div class="orch-traj-turn">'
        f"{USAGE_SEPARATOR.join(segments)}{cache_hit}</div>"
    )
