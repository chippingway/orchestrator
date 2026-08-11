# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Every color the analytics page and the charts inside it are painted in.

Two vocabularies sit here. The chrome and semantic colors are the standalone
mock's `:root` block -- a cool gray page, white cards, an indigo accent, and
the positive / warning / negative trio a delta pill and an insight banner are
tinted from -- so a Plotly trace and the card it is drawn inside come from one
set of values. `.streamlit/config.toml` mirrors the same block into Streamlit's
own `[theme]` for that reason.

The categorical maps beneath them pin a dimension value to a hue: an event
kind, a workflow stage, a cost source, a token type, a backend, an agent role,
a review round. A map rather than a per-chart choice is what keeps a value the
same color on every panel and across sessions, so an operator reading two
panels side by side is reading one legend. A value no map covers falls through
to `color_for` and the ordered `CATEGORICAL_PALETTE` behind it.

Nothing here imports Plotly. A caller that only needs a color -- the page
banner drawn before any figure exists -- must not pay for the optional
`dashboard` dependency group to read one.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Optional, Sequence

# Page chrome, straight off the mock's `:root` block: a cool gray page with
# white cards, and three ink tints the label, the value, and the caption on a
# card are separated by.
BACKGROUND = "#f4f5f8"
CARD_BG = "#ffffff"
SURFACE = "#f0f1f6"        # mock --chip-bg
TEXT = "#1c2030"           # mock --ink
MUTED_TEXT = "#565d72"     # mock --ink-2
MUTED_TEXT_SOFT = "#8a90a3"  # mock --ink-3
GRID = "#eef0f5"           # mock --grid
BORDER = "#e6e8ef"         # mock --border

# Brand / semantic colors used by KPI deltas and insight banners.
_INDIGO = "#5b6cf0"
_ORANGE = "#e0913a"
_RED = "#d9534a"
ACCENT = "#5b54e0"
PRIMARY = ACCENT
SECONDARY = "#8b5cf6"
SUCCESS = "#2f9e6b"        # mock --pos
WARNING = _ORANGE
DANGER = _RED               # mock --neg
NEUTRAL = "#6b7280"
INK = TEXT

# Token-type segments for the hero spend & token usage chart. The three hues
# are tuned to read against the cool gray page background and stack in the
# order Input / Output / Cache from bottom to top.
TOKEN_TYPE_COLORS: Mapping[str, str] = MappingProxyType({
    "Input": _INDIGO,
    "Output": _ORANGE,
    "Cache": "#1aa39a",
})

# Agent backends. `claude` is the developer / implementer; `codex` is the
# reviewer. Keys match the strings the tracked-run accounting writes to
# `backend`. `unknown` covers NULL rows from the read model.
BACKEND_COLORS: Mapping[str, str] = MappingProxyType({
    "claude": ACCENT,
    "codex": _ORANGE,
    "unknown": NEUTRAL,
})

# Agent roles used by the review-cycle cost split. Keys match the `agent_role`
# a tracked run is recorded under.
AGENT_ROLE_COLORS: Mapping[str, str] = MappingProxyType({
    "developer": ACCENT,
    "reviewer": _ORANGE,
})

# Review-round buckets, in the order the chart renders them: the `0` bucket is
# the initial pass; everything past it is rework.
REVIEW_ROUND_COLORS: Mapping[str, str] = MappingProxyType({
    "0": _INDIGO,
    "1": "#e8a13a",
    "2": "#e07a3a",
    "3": "#dd6a3c",
    "4": _RED,
    "5": "#c33f37",
    "3-5": _RED,
    "6+": "#a8201e",
    "unknown": NEUTRAL,
})

# Deterministic fallback palette for dimensions without an explicit mapping.
# Order is significant -- `color_for("foo", ["foo", "bar"])` returns the n-th
# entry for the n-th distinct value, so two charts rendering the same domain in
# the same order produce the same colors.
CATEGORICAL_PALETTE: tuple[str, ...] = (
    ACCENT,
    _INDIGO,
    _ORANGE,
    "#1aa39a",
    "#8b5cf6",
    _RED,
    "#d98a3a",
    "#6b7a99",
    "#0ea5e9",
    "#65a30d",
)

# Analytics event kinds written by the recording owners' `append_record`.
EVENT_COLORS: Mapping[str, str] = MappingProxyType({
    "stage_enter": ACCENT,
    "stage_evaluation": NEUTRAL,
    "agent_exit": SUCCESS,
})

# Workflow stage labels. Mirror the labels carried on live GitHub issues;
# renaming any one of them would also have to update the state machine, so the
# mapping is a public contract.
STAGE_COLORS: Mapping[str, str] = MappingProxyType({
    "decomposing": "#8b5cf6",
    "blocked": NEUTRAL,
    "ready": _INDIGO,
    "umbrella": SECONDARY,
    "implementing": _INDIGO,
    "validating": _ORANGE,
    "documenting": "#1aa39a",
    "in_review": "#7c3aed",
    "fixing": _RED,
    "resolving_conflict": "#d98a3a",
    "question": "#6b7a99",
    "discussion": "#0ea5e9",
    "done": SUCCESS,
    "rejected": NEUTRAL,
})

# `cost_source` values from `observability/usage/metrics.py`'s `UsageMetrics`.
COST_SOURCE_COLORS: Mapping[str, str] = MappingProxyType({
    "reported": SUCCESS,
    "estimated": WARNING,
    "unknown-price": DANGER,
    "unknown": NEUTRAL,
    "no-usage": NEUTRAL,
})


def color_for(
    key: str,
    domain: Optional[Sequence[str]] = None,
    *,
    explicit: Optional[Mapping[str, str]] = None,
) -> str:
    """Resolve `key` to a hex color string.

    Lookup order:

    1. `explicit` (caller-supplied override, typically one of the
       module-level palettes such as `STAGE_COLORS`).
    2. Position of `key` inside `domain` if both are provided -- the
       n-th distinct value gets the n-th entry of
       `CATEGORICAL_PALETTE`, wrapping when `len(domain)` exceeds the
       palette length.
    3. Hash-based fallback so a single key still gets a stable color
       without a domain. The hash fallback uses Python's stable
       `hash(...)` modulus against the palette length; this is fine
       for visual stability *within* a process but not across processes
       (Python salts the hash). Callers that need cross-process
       stability should always pass `domain`.
    """
    if explicit is not None and key in explicit:
        return explicit[key]
    if domain is not None:
        try:
            idx = list(domain).index(key)
        except ValueError:
            idx = None
        if idx is not None:
            return CATEGORICAL_PALETTE[idx % len(CATEGORICAL_PALETTE)]
    return CATEGORICAL_PALETTE[hash(key) % len(CATEGORICAL_PALETTE)]
