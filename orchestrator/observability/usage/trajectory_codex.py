# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Reconstruct an ordered Codex trajectory from its stream items.

Codex emits several frames per operation -- started, then any updates, then
completed -- so this owner correlates them by `item.id` and keeps each item at
the position its first frame took. `trajectory_codex_items` beside it decides
what each item type contributes, down to which frame's invocation an item is
recorded under; everything here is the correlation, the ordering, and the
frames a stream can carry without an id at all.

The id is what makes an operation one item rather than several, so a wrapper
frame reporting the id of the call nested inside it merges into that call
instead of doubling it -- and, when the wrapper is of a type nothing
normalizes, it neither replaces the normalized pair with a placeholder nor
adds one beside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from orchestrator.observability.usage import (
    protocol,
    trajectory_codex_items as codex_items,
)
from orchestrator.observability.usage.trajectory_models import TrajectoryStep


def final_output(events: Iterable[dict[str, Any]]) -> Optional[str]:
    final_text: Optional[str] = None
    for event in events:
        stream_item = event.get(protocol.ITEM_KEY)
        if not isinstance(stream_item, dict):
            continue
        if stream_item.get(protocol.TYPE) != codex_items.AGENT_MESSAGE:
            continue
        candidate = stream_item.get(codex_items.TEXT)
        if isinstance(candidate, str):
            final_text = candidate
    return final_text


def trajectory_steps(
    events: Iterable[dict[str, Any]],
) -> tuple[TrajectoryStep, ...]:
    builder = CodexTrajectoryBuilder()
    for event in events:
        builder.add_event(event)
    return builder.build()


@dataclass
class CodexTrajectoryBuilder:
    """Frames folded into one record per item, in first-seen order."""

    order: list[str] = field(default_factory=list)
    by_id: dict[str, codex_items.CodexItemPayloads] = field(default_factory=dict)
    anonymous: list[TrajectoryStep] = field(default_factory=list)

    def add_event(self, event: dict[str, Any]) -> None:
        stream_item = event.get(protocol.ITEM_KEY)
        if not isinstance(stream_item, dict):
            return
        payloads = codex_items.normalize_item(
            stream_item,
            event.get(protocol.TYPE) == codex_items.ITEM_COMPLETED,
        )
        if payloads is None:
            return
        item_id = self._item_id(stream_item)
        if item_id:
            self._absorb(item_id, payloads)
            return
        # Nothing correlates frames a stream left unidentified, so each one
        # stands on its own and trails the ordered items rather than claiming
        # a position between two of them.
        self.anonymous.extend(payloads.steps(""))

    def build(self) -> tuple[TrajectoryStep, ...]:
        steps: list[TrajectoryStep] = []
        for item_id in self.order:
            steps.extend(self.by_id[item_id].steps(item_id))
        steps.extend(self.anonymous)
        return tuple(steps)

    def _item_id(self, stream_item: dict[str, Any]) -> str:
        raw_id = stream_item.get(protocol.ID)
        return raw_id if isinstance(raw_id, str) else ""

    def _absorb(
        self,
        item_id: str,
        payloads: codex_items.CodexItemPayloads,
    ) -> None:
        recorded = self.by_id.get(item_id)
        if recorded is None:
            self.order.append(item_id)
            self.by_id[item_id] = payloads
            return
        placeholder = codex_items.UNSUPPORTED_ITEM
        if payloads.kind == placeholder and recorded.kind != placeholder:
            # One operation is one item however many frames wrap it. A frame
            # nothing claims -- an outer tool call the parser has no
            # normalizer for, reporting the same id as the web search or MCP
            # call nested inside it -- neither demotes the pair another frame
            # already named nor becomes a second step beside it. The reverse
            # order needs no rule of its own: a claimed frame arriving after
            # the placeholder overwrites its kind, name, and payloads through
            # the merge below.
            return
        recorded.kind = payloads.kind
        recorded.name = payloads.name or recorded.name
        if payloads.contributes_call(recorded.call_payload):
            recorded.call_payload = payloads.call_payload
        if payloads.result_payload is not codex_items.MISSING:
            recorded.result_payload = payloads.result_payload
