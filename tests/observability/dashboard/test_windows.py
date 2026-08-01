# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The span a page reports over, and the one its deltas compare against."""

from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import windows
from tests.observability.dashboard import dashboard_test_support as fixtures


_WINDOW_DAYS = 7


class DefaultDateRangeTest(unittest.TestCase):
    """The range a page opens on spans `days` ending today, inclusive."""

    def test_window_includes_today_and_n_days(self) -> None:
        start, end = windows.default_date_range(
            today=fixtures.MAY28, days=_WINDOW_DAYS,
        )
        self.assertEqual(end, fixtures.MAY28)
        self.assertEqual(start, fixtures.MAY22)

    def test_days_one_yields_today_only(self) -> None:
        start, end = windows.default_date_range(today=fixtures.MAY28, days=1)
        self.assertEqual(start, end)

    def test_days_zero_clamps_to_today_only(self) -> None:
        # `days=0` is non-sensical (an empty window) so the helper clamps to
        # "today only" instead of returning end < start.
        start, end = windows.default_date_range(today=fixtures.MAY28, days=0)
        self.assertEqual(start, fixtures.MAY28)
        self.assertEqual(end, fixtures.MAY28)


class ToWindowTest(unittest.TestCase):
    """A pair of picked dates becomes a half-open UTC window."""

    def test_inclusive_end_becomes_exclusive_midnight(self) -> None:
        # The reads are bounded by `ts < end`; midnight on the day after
        # `end_date` is what makes events from `end_date` visible.
        window = windows.to_window(fixtures.MAY01, fixtures.MAY03)
        self.assertEqual(window.start, fixtures.utc_midnight(fixtures.MAY01))
        self.assertEqual(window.end, fixtures.utc_midnight(fixtures.MAY04))

    def test_reversed_range_is_swapped(self) -> None:
        # The Streamlit two-date input lets the user type end < start.
        # Swapping silently keeps the dashboard useful instead of collapsing
        # to an empty SQL window.
        window = windows.to_window(fixtures.MAY05, fixtures.MAY01)
        self.assertEqual(window.start.date(), fixtures.MAY01)
        self.assertEqual(window.end.date(), fixtures.MAY06)

    def test_single_day_window(self) -> None:
        window = windows.to_window(fixtures.MAY01, fixtures.MAY01)
        self.assertEqual(window.start, fixtures.utc_midnight(fixtures.MAY01))
        self.assertEqual(window.end, fixtures.utc_midnight(fixtures.MAY02))


class PreviousWindowTest(unittest.TestCase):
    """The previous-window helper feeds the KPI delta column.

    It returns a window of the same length immediately before the current one
    so the deltas compare like-for-like (e.g. the last seven days against the
    seven days before those).
    """

    def test_length_preserved(self) -> None:
        current = windows.to_window(fixtures.MAY01, fixtures.MAY07)
        previous = windows.previous_window(current)
        self.assertEqual(previous.end, current.start)
        self.assertEqual(
            previous.end - previous.start, current.end - current.start,
        )

    def test_seven_day_window_has_seven_day_prior(self) -> None:
        current = windows.to_window(fixtures.MAY22, fixtures.MAY28)
        previous = windows.previous_window(current)
        # `to_window`'s end is exclusive (one day past `end_date`), so the
        # seven-day window spans 7 calendar days; the previous window starts
        # seven days before the current start.
        self.assertEqual(previous.start.date(), fixtures.MAY15)
        self.assertEqual(previous.end.date(), fixtures.MAY22)


if __name__ == "__main__":
    unittest.main()
