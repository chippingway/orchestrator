# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The calendar the window cases are dated in, and the extents over it.

Every module here reads the same dates, because the arithmetic under test is
what one date means relative to another -- a preset clamped at the extent's
min and a previous window measured back from a start are the same span read
from opposite ends, and naming the days once is what keeps the two cases
comparable. The whole namespace is imported rather than the individual dates:
a case names more of them than an import list should carry.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from orchestrator.observability.analytics.query.overview_models import DataExtent


_YEAR = 2026

_APRIL = 4

# The day of the month a thirty-day span anchored at May 28 starts on, which
# is why the calendar here reaches back into the month before May at all.
_THIRTY_DAY_START = 29

_MAY = 5

# The final minute of a day, so an extent's max lands late inside its own date
# rather than on the midnight the window boundaries are aligned to.
_LAST_HOUR = 23

_LAST_MINUTE = 59

JAN01 = date(_YEAR, 1, 1)

APR29 = date(_YEAR, _APRIL, _THIRTY_DAY_START)

MAY01 = date(_YEAR, _MAY, 1)

MAY02 = date(_YEAR, _MAY, 2)

MAY03 = date(_YEAR, _MAY, 3)

MAY04 = date(_YEAR, _MAY, 4)

MAY05 = date(_YEAR, _MAY, 5)

MAY06 = date(_YEAR, _MAY, 6)

MAY07 = date(_YEAR, _MAY, 7)

MAY15, MAY22 = (
    date(_YEAR, _MAY, day_of_month) for day_of_month in (15, 22)
)

MAY26, MAY28, MAY29 = (
    date(_YEAR, _MAY, day_of_month) for day_of_month in (26, 28, 29)
)


def utc_midnight(day: date) -> datetime:
    """The instant a window boundary on `day` is aligned to."""
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def data_extent(first: date, last: date) -> DataExtent:
    """An extent whose rows run from `first` to the last minute of `last`."""
    return DataExtent(
        min_ts=utc_midnight(first),
        max_ts=datetime(
            last.year,
            last.month,
            last.day,
            _LAST_HOUR,
            _LAST_MINUTE,
            tzinfo=UTC,
        ),
    )
