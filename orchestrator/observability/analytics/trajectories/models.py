# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one trajectory record keeps whole, and the sizes it is kept within.

One owner for everything a record is measured against: the always-retained
headline charged before any variable array, the running total those arrays are
drawn from, and the three caps the whole thing is bounded by -- the per-field
head and tail a single value is truncated to, and the serialized byte budget
one record may not exceed.

The caps are defaults rather than environment knobs, so they are read back off
a *settings holder* rather than parsed: the analytics package republishes them
as ``_TRAJECTORY_FIELD_HEAD`` / ``_TRAJECTORY_FIELD_TAIL`` /
``_TRAJECTORY_RECORD_BUDGET``, which is where a caller shrinks one to bound a
run it is about to record. ``limits_on`` is a view over that holder, reading
each cap when asked, so a value patched between two records reaches the second
one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

TRAJECTORY_FIELD_HEAD = 2000
TRAJECTORY_FIELD_TAIL = 2000
TRAJECTORY_RECORD_BUDGET = 200_000


@dataclass(frozen=True)
class TrajectoryLimits:
    """The three caps as they stand on one settings holder."""

    holder: Any

    @property
    def field_head(self) -> int:
        return self.holder._TRAJECTORY_FIELD_HEAD

    @property
    def field_tail(self) -> int:
        return self.holder._TRAJECTORY_FIELD_TAIL

    @property
    def record_budget(self) -> int:
        return self.holder._TRAJECTORY_RECORD_BUDGET


@dataclass(frozen=True)
class TrajectoryHeadline:
    """Always-retained trajectory fields charged before variable arrays."""

    user_input: Optional[str]
    system_prompt: Optional[str]
    output: Optional[str]
    run_usage: dict[str, Any]

    @property
    def serialized_size(self) -> int:
        text_fields = (self.user_input, self.system_prompt, self.output)
        text_size = sum(len(text_field or "") for text_field in text_fields)
        return text_size + len(json.dumps(self.run_usage, default=str))


@dataclass
class TrajectoryBudget:
    """Track serialized variable-field bytes retained in one record."""

    used: int
    limit: int
    truncated: bool = False

    def include(self, field_value: Any) -> bool:
        self.used += len(json.dumps(field_value, default=str))
        if self.used <= self.limit:
            return True
        self.truncated = True
        return False


def limits_on(holder: Any) -> TrajectoryLimits:
    """Read the caps in force off the settings holder a write is bound to."""
    return TrajectoryLimits(holder)
