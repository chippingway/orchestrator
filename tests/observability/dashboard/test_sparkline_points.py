# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Where a KPI tile's sparkline puts the days behind one window."""
from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import sparkline_points

# The box a tile draws a line in, and the inset the line is laid out inside.
_WIDTH = 96

_HEIGHT = 26

_INSET = 2

# The three horizontal positions three days land on, and the two vertical ones
# the highest and lowest of them do.
_FIRST_X = 2.0

_MIDDLE_X = 48.0

_LAST_X = 94.0

_TOP_Y = 2.0

_MIDDLE_Y = 13.0

_BOTTOM_Y = 24.0

# A window that rose across three days, one that never moved, one whose middle
# day the read answered with a null and the same window with that day spelled
# as a zero, and one that reported nothing at all.
_RISING = (1.0, 2.0, 3.0)

_FLAT = (5.0, 5.0)

_ZERO = float()

_WITH_A_NULL = (1.0, None, 3.0)

_WITH_A_ZERO = (1.0, _ZERO, 3.0)

_ALL_ZERO = (_ZERO, _ZERO, _ZERO)

# The two day counts a box is divided between, and the distance each leaves:
# three days share the drawable width, and one day is given all of it.
_THREE_DAYS = 3

_ONE_DAY = 1

_THREE_DAY_STEP = 46.0

_ONE_DAY_STEP = 92.0


_Days = tuple[float | None, ...]


def _projected(days: _Days) -> list[tuple[float, float]]:
    return sparkline_points.sparkline_points(
        days, width=_WIDTH, height=_HEIGHT,
    )


class WindowProjectionTest(unittest.TestCase):
    """A line this narrow carries no axis, so what it says is its shape: the
    days are spread across the whole box and scaled to the window's own range
    rather than to zero.
    """

    def test_a_window_is_drawn_across_its_own_range(self) -> None:
        self.assertEqual(
            _projected(_RISING),
            [
                (_FIRST_X, _BOTTOM_Y),
                (_MIDDLE_X, _MIDDLE_Y),
                (_LAST_X, _TOP_Y),
            ],
        )

    def test_a_null_day_counts_as_a_zero(self) -> None:
        # A read answers a day nothing ran on with a null, and the tile above
        # reports that day as none rather than dropping it, so the line has to
        # be scaled against it too.
        self.assertEqual(_projected(_WITH_A_NULL), _projected(_WITH_A_ZERO))

    def test_the_step_always_has_an_interval(self) -> None:
        # A one-day window has no gap between days to divide the width by, so
        # the step falls back to the whole of it rather than raising.
        cases = (
            (_THREE_DAYS, _THREE_DAY_STEP),
            (_ONE_DAY, _ONE_DAY_STEP),
        )
        for sample_count, step in cases:
            with self.subTest(sample_count=sample_count):
                self.assertEqual(
                    sparkline_points.sparkline_step(
                        _WIDTH, _INSET, sample_count,
                    ),
                    step,
                )


class QuietWindowTest(unittest.TestCase):
    """The two windows with no range to scale against, kept apart: one still
    has a line to draw and the other has nothing worth drawing.
    """

    def test_a_flat_window_settles_on_the_baseline(self) -> None:
        # Every day equal leaves no range to divide by, so the span floors
        # rather than the projection raising.
        self.assertEqual(
            _projected(_FLAT), [(_FIRST_X, _BOTTOM_Y), (_LAST_X, _BOTTOM_Y)],
        )

    def test_a_window_of_nothing_draws_no_line(self) -> None:
        # A window that reported nothing would draw the same baseline the flat
        # one above does, so it is left undrawn instead of reading as a window
        # that merely never rose.
        for days in ((), _ALL_ZERO, (None,)):
            with self.subTest(days=days):
                self.assertEqual(_projected(days), [])


if __name__ == "__main__":
    unittest.main()
