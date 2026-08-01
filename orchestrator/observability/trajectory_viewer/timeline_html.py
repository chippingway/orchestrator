# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The header one timeline entry is read by, and where a usage strip belongs.

An entry's header is its position, what kind of step it was, and whatever
identifies it -- a tool name, a tool id, or neither. The kind is looked up in
one vocabulary so a badge's wording and its color always agree, and a kind this
viewer has no wording for still renders: it falls back to the tool-result
styling and prints the kind verbatim, because a record written by a newer sink
is worth reading unlabelled rather than losing its step. The step number is
rendered one-based, since the index is the caller's loop counter and an
operator counting steps starts at one.

The two brackets the read model wraps a run in are the reason the vocabulary is
keyed on the shared constants rather than on literals: the prompt and the final
output are entries the timeline synthesized, not steps the sink wrote, and they
carry the badges the page names them by.

Which entry gets a usage strip above it is decided here rather than by the
renderer walking the list. A strip belongs to an assistant turn, and a turn
spans several entries, so it is drawn once at the first entry carrying a new
turn index -- the later entries of that turn, and the turn inputs carrying no
index at all, are paired with nothing. That pairing is what the strip's own
copy promises an operator, so it is decided in one place.

Every value that reaches the markup is escaped first: a page writes these with
``unsafe_allow_html=True``, and a tool name, a tool id, and an unrecognized
kind are all record text this viewer does not own.
"""

from __future__ import annotations

import html
from types import MappingProxyType
from typing import Mapping, Optional

from orchestrator.observability.trajectory_viewer import constants
from orchestrator.observability.trajectory_viewer.models import (
    TimelineEntry,
    TurnUsageView,
)
from orchestrator.observability.trajectory_viewer.runs import TrajectoryRun


TimelineUsagePair = tuple[Optional[TurnUsageView], TimelineEntry]
BADGE_BY_KIND: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        constants.TIMELINE_PROMPT: ("prompt", "prompt"),
        constants.TIMELINE_OUTPUT: ("output", "final output"),
        "tool_call": ("call", "tool call"),
        "tool_result": ("result", "tool result"),
        "assistant_message": ("assistant", "assistant"),
        "user_message": ("user", "user turn"),
    }
)


def timeline_entry_html(entry: TimelineEntry, index: int) -> str:
    """Render one typed timeline entry."""
    badge_class, badge_text = BADGE_BY_KIND.get(
        entry.kind,
        ("result", entry.kind or "step"),
    )
    name_html = (
        f'<span class="orch-traj-step-name">{html.escape(entry.name)}</span>'
        if entry.name
        else ""
    )
    identifier_html = (
        f'<span class="orch-traj-step-id">{html.escape(entry.tool_id)}</span>'
        if entry.tool_id
        else ""
    )
    step_number = index + 1
    return (
        '<div class="orch-traj-step">'
        f'<span class="orch-traj-step-idx">{step_number}</span>'
        f'<span class="orch-traj-badge {badge_class}">'
        f"{html.escape(badge_text)}</span>{name_html}{identifier_html}</div>"
    )


def timeline_with_usage(run: TrajectoryRun) -> list[TimelineUsagePair]:
    """Pair the first entry of each assistant turn with its usage strip."""
    paired: list[TimelineUsagePair] = []
    previous_turn: Optional[int] = None
    for entry in run.timeline:
        strip = None
        if entry.turn is not None and entry.turn != previous_turn:
            strip = run.usage_for_turn(entry.turn)
            previous_turn = entry.turn
        paired.append((strip, entry))
    return paired
