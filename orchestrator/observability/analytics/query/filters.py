# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What one read filters by, and the clause a filter set accumulates into.

`WindowFilters` is the selection every read family accepts -- the window
bounds, the repo, the issue, and the event / stage multiselects -- carried as
one value, so a dimension the dashboard threads into one aggregate reaches all
of them. Its three projections are how a caller narrows that set: for a view
with no `event` column, for repo-level catalog rows, and for a session's
evidence from before the window.

`WhereBuilder` accumulates one parameterized predicate and the bindings that go
with it. Each condition is appended together with its operand, so the order of
the `%s` markers in the rendered clause is the order of the values handed to
the driver -- the two cannot drift apart because neither is built separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Sequence


@dataclass(frozen=True)
class WindowFilters:
    """The common window and selection filters accepted by readers."""

    start: datetime | None = None
    end: datetime | None = None
    repo: str | None = None
    events: Sequence[str] | None = None
    stages: Sequence[str] | None = None
    issue: int | None = None

    def without_events(self) -> WindowFilters:
        """Return filters suitable for a view with no `event` column."""
        return replace(self, events=None)

    def catalog_scope(self) -> WindowFilters:
        """Return the date/repo subset valid for repo-level catalog rows."""
        return replace(self, events=None, stages=None, issue=None)

    def historical_scope(self) -> WindowFilters:
        """Return filters for a session's evidence before the window end.

        Drops the ``start`` bound and the ``stages`` / ``events``
        selections while keeping ``end`` / ``repo`` / ``issue``, so a
        logical session's loads from a prior stage or from before the
        reporting window stay visible, yet the ``end`` bound still stops
        later evidence from leaking backward into the aggregate.
        """
        return replace(self, start=None, events=None, stages=None)


@dataclass
class WhereBuilder:
    """Accumulate one parameterized SQL predicate and its values."""

    conditions: list[str] = field(default_factory=list)
    bindings: list[Any] = field(default_factory=list)

    def add_scalar(
        self,
        column: str,
        operand: Any,
        *,
        operator: str = "=",
    ) -> None:
        if operand is None:
            return
        self.conditions.append(f"{column} {operator} %s")
        self.bindings.append(operand)

    def add_selection(
        self,
        column: str,
        selection: Sequence[str] | None,
    ) -> None:
        if selection is None:
            return
        if not selection:
            self.conditions.append("FALSE")
            return
        placeholders = ", ".join("%s" for _ in selection)
        self.conditions.append(f"{column} IN ({placeholders})")
        self.bindings.extend(selection)

    def render(self) -> tuple[str, list[Any]]:
        if not self.conditions:
            return "", self.bindings
        where_clause = " AND ".join(self.conditions)
        return f" WHERE {where_clause}", self.bindings
