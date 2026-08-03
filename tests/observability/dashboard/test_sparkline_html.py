# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The inline SVG a KPI tile's sparkline is written as."""
from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import sparkline_html

# One projected window, and the two strings it is written as: the line stroked
# through those days, and the fill closed along the bottom of the box.
_POINTS = ((2.0, 24.0), (48.0, 13.0), (94.0, 2.0))

_POLYLINE = "2.0,24.0 48.0,13.0 94.0,2.0"

_AREA = "M2.0,24.0 L2.0,24.0 L48.0,13.0 L94.0,2.0 L94.0,24.0 Z"

# A projected day carrying more precision than the markup does.
_LONG_POINT = (2.0, 16.666666666666668)

_ROUNDED_POINT = "2.0,16.7"

# The box a caller asks for, and the days and hue it asks to draw in it.
_WIDTH = 40

_HEIGHT = 12

_COLOR = "#111"

_RISING = (1.0, 2.0, 3.0)

_ZERO = float()

_ZEROS = (_ZERO, _ZERO)

# The box a tile draws in when a caller names none.
_DEFAULT_WIDTH = 96

_DEFAULT_HEIGHT = 26


def _rendered(series: tuple[float, ...], width: int, height: int) -> str:
    return sparkline_html.render_sparkline(
        sparkline_html.SparklineRequest(
            samples=series, color=_COLOR, width=width, height=height,
        ),
    )


class SparklinePathsTest(unittest.TestCase):
    """Both strings are written from one projection, because they trace the
    same days and differ only in how they end.
    """

    def test_a_window_is_written_as_both_paths(self) -> None:
        paths = sparkline_html.sparkline_paths(_POINTS, height=_DEFAULT_HEIGHT)
        self.assertEqual(paths.polyline, _POLYLINE)
        self.assertEqual(paths.area, _AREA)

    def test_a_point_is_rounded_to_one_decimal(self) -> None:
        self.assertEqual(
            sparkline_html.sparkline_point_text(_LONG_POINT), _ROUNDED_POINT,
        )


class RenderedSparklineTest(unittest.TestCase):
    """What a tile carries: a line in the box the caller asked for, or that
    same box left empty.
    """

    def test_a_drawn_line_carries_the_box_and_hue(self) -> None:
        svg = _rendered(_RISING, _WIDTH, _HEIGHT)
        self.assertIn(f'width="{_WIDTH}" height="{_HEIGHT}"', svg)
        self.assertIn(f'viewBox="0 0 {_WIDTH} {_HEIGHT}"', svg)
        # The fill and the stroke are the same hue, so the tint under a line
        # cannot end up reading as a second series beside it.
        self.assertIn(f'fill="{_COLOR}"', svg)
        self.assertIn(f'stroke="{_COLOR}"', svg)

    def test_an_empty_window_holds_the_tile_room(self) -> None:
        # Nothing to draw still renders the box, so a strip whose windows are
        # not all alike keeps its tiles lined up.
        svg = _rendered(_ZEROS, _WIDTH, _HEIGHT)
        self.assertEqual(
            svg,
            f'<svg width="{_WIDTH}" height="{_HEIGHT}" '
            f'viewBox="0 0 {_WIDTH} {_HEIGHT}"></svg>',
        )


class KeywordSurfaceTest(unittest.TestCase):
    """The spellings a caller has always passed, kept callable by name."""

    def test_the_historical_keywords_still_bind(self) -> None:
        self.assertEqual(
            sparkline_html.sparkline_svg(
                values=_RISING, color=_COLOR, w=_WIDTH, h=_HEIGHT,
            ),
            _rendered(_RISING, _WIDTH, _HEIGHT),
        )

    def test_an_unnamed_box_is_the_tile_size(self) -> None:
        self.assertEqual(
            sparkline_html.sparkline_svg(_RISING, color=_COLOR),
            _rendered(_RISING, _DEFAULT_WIDTH, _DEFAULT_HEIGHT),
        )


if __name__ == "__main__":
    unittest.main()
