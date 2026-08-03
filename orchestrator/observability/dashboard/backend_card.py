# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a run on one backend is worth, and the card it is read off.

One card per backend answers a single question -- what work on this agent
costs -- so the three readings behind it sit beside the markup rather than in
the page drawing it: what a million tokens cost, what one run cost, and how
much of the billable input arrived out of cache. Each is a ratio whose
denominator can be zero on a window a backend barely ran in, so all three go
through one guard that answers nothing rather than raising, and a card reading
zero everywhere is what an operator sees instead of a page that stopped.

What counts as a token is the whole billed band -- input, output, cache read,
and cache write -- because that is what the spend printed beside it was charged
for. Cache leverage is the narrower reading of the same row: cache reads over
the input they stood in for, which is the share of *billable input* the cache
answered rather than the share of every token it touched.

The theme is a parameter rather than an import, the way every card builder on
this page is handed one: a page resolves a single theme object and passes it
down, so the border, the type, and the per-backend hue a card is drawn in are
the ones the chrome and charts around it were drawn from. The backend name
reaches this owner off the sink rather than out of this repository, so it is
escaped into the markup a browser is asked to interpret.
"""
from __future__ import annotations

import html
from dataclasses import dataclass

from orchestrator.observability.analytics.query.cost_models import (
    BackendEfficiencyRow,
)


_TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class BackendEfficiencyMetrics:
    tokens: int
    cost_per_million: float
    cost_per_run: float
    cache_hit_pct: float


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return float()
    return numerator / denominator


def backend_efficiency_metrics(
    row: BackendEfficiencyRow,
) -> BackendEfficiencyMetrics:
    tokens = int(
        (row.total_input_tokens or 0)
        + (row.total_output_tokens or 0)
        + (row.total_cache_read_tokens or 0)
        + (row.total_cache_write_tokens or 0)
    )
    cache_read = int(row.total_cache_read_tokens or 0)
    cache_input_total = cache_read + int(row.total_input_tokens or 0)
    return BackendEfficiencyMetrics(
        tokens=tokens,
        cost_per_million=safe_ratio(
            row.total_cost_usd,
            tokens / _TOKENS_PER_MILLION,
        ),
        cost_per_run=safe_ratio(row.total_cost_usd, row.runs),
        cache_hit_pct=safe_ratio(cache_read, cache_input_total) * 100,
    )


def backend_efficiency_card_html(row: BackendEfficiencyRow, *, theme) -> str:
    """Render one backend-efficiency card to inline HTML."""
    metrics = backend_efficiency_metrics(row)
    color = theme.color_for(row.backend, explicit=theme.BACKEND_COLORS)
    return (
        f'<div style="border:1px solid {theme.BORDER};'
        "border-radius:8px;padding:10px 12px;"
        'margin-bottom:8px">'
        '<div style="display:flex;align-items:center;'
        'gap:8px;margin-bottom:4px">'
        '<span style="display:inline-block;width:10px;'
        f'height:10px;border-radius:50%;background:{color}">'
        "</span>"
        f'<b style="color:{theme.TEXT}">{html.escape(row.backend)}</b>'
        f'<span style="color:{theme.MUTED_TEXT};'
        'font-size:12px;margin-left:auto">'
        f'{row.runs} runs · {theme.fmt_tokens(metrics.tokens)} tok'
        "</span></div>"
        f'<div style="color:{theme.TEXT};font-size:20px;'
        "font-weight:600;"
        f'font-family:{theme.MONO_FONT_FAMILY};margin-bottom:6px">'
        f"{html.escape(theme.fmt_money_exact(row.total_cost_usd))}"
        f'<span style="color:{theme.MUTED_TEXT};'
        "font-size:11px;margin-left:8px;"
        f'font-family:{theme.FONT_FAMILY}">spend</span></div>'
        '<div style="display:flex;gap:14px;font-size:12px;'
        f'color:{theme.MUTED_TEXT}">'
        f"<span>${metrics.cost_per_million:.2f} / 1M tok</span>"
        f"<span>{metrics.cache_hit_pct:.0f}% cache hit</span>"
        f"<span>${metrics.cost_per_run:.2f} / run</span>"
        "</div></div>"
    )
