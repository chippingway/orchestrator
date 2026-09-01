# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Reading one cell off a row the day-bucketed rollup answered with.

Three readings stand between a raw cell and the frozen result field it lands
in. A column an older, narrower fixture never carried is read positionally
against a caller-chosen default, so a row shorter than the SELECT list still
round-trips instead of raising on the unpack. A nullable USD cost is read as a
float with a NULL and a missing column collapsing to the same zero, because a
spend field the dashboard sums cannot carry `None`. And a `day` some drivers
widen to a timestamp is narrowed back to the date the rollup grouped by, so a
page keying its series on days is not comparing a date against midnight.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any


def row_value(row: Sequence[Any], index: int, default: Any = 0) -> Any:
    """Read one positional cell off a row that may be shorter than it."""
    if len(row) <= index:
        return default
    return row[index]


def cost_cell(row: Sequence[Any], index: int) -> float:
    """Read a nullable USD cost column as a float, treating null/missing as zero."""
    return float(row_value(row, index) or 0)


def day_value(day: Any) -> Any:
    """Narrow a widened `day` column back to the date the rollup grouped by."""
    if isinstance(day, datetime):
        return day.date()
    return day
