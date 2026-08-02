# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard usage-over-time chart tests."""

import importlib


import unittest


from datetime import date


def _load_chart_dependencies():
    charts = importlib.import_module("orchestrator.dashboard_charts")
    theme_module = importlib.import_module("orchestrator.dashboard_theme")
    read_module = importlib.import_module("orchestrator.analytics.read")
    return charts, theme_module, read_module


try:
    dashboard_charts, theme, _analytics_read = _load_chart_dependencies()
except ModuleNotFoundError:
    HAS_PLOTLY = False
    dashboard_charts = None  # type: ignore[assignment]
else:
    HAS_PLOTLY = True
    HourlyHeatmapPoint = _analytics_read.HourlyHeatmapPoint
    RepoBreakdownRow = _analytics_read.RepoBreakdownRow
    ReviewRoundBucketRow = _analytics_read.ReviewRoundBucketRow
    StageBreakdown = _analytics_read.StageBreakdown
    ThroughputDayRow = _analytics_read.ThroughputDayRow
    TimeSeriesPoint = _analytics_read.TimeSeriesPoint


_SKIP_REASON = "plotly not installed -- run `uv sync --group dashboard`"


EVENT_AGENT_EXIT = "agent_exit"


TRACE_COST = "Cost"


_YEAR = 2026


_DAY1 = date(_YEAR, 5, 1)


_DAY2 = date(_YEAR, 5, 2)


_HERO_HEIGHT = 330


_COST_USD = 1.2


_INPUT_TOKENS = 1000


_OUTPUT_TOKENS = 500


@unittest.skipUnless(HAS_PLOTLY, _SKIP_REASON)
class UsageOverTimeTest(unittest.TestCase):
    """The hero chart assembles the token stack, the cost overlay, and the
    two aligned axes into one figure at the height the panel above the KPI
    strip is laid out around, and answers a window with no rows in it with
    the shared placeholder instead.
    """

    def test_the_stack_and_overlay_are_one_figure(self) -> None:
        points = [
            TimeSeriesPoint(
                day=day,
                event=EVENT_AGENT_EXIT,
                count=1,
                cost_usd=_COST_USD,
                input_tokens=_INPUT_TOKENS,
                output_tokens=_OUTPUT_TOKENS,
            )
            for day in (_DAY1, _DAY2)
        ]
        fig = dashboard_charts.usage_over_time(points)
        names = [trace.name for trace in fig.data]
        self.assertEqual(names[-1], TRACE_COST)
        self.assertGreater(len(names), 1)
        # The overlay is drawn against the axis the layout gave it, so the
        # cost line lands on the dollar scale rather than the token one.
        cost_trace = next(
            trace for trace in fig.data if trace.name == TRACE_COST
        )
        self.assertEqual(cost_trace.yaxis, "y2")
        self.assertIsNotNone(fig.layout.yaxis2.range)

    def test_empty_renders_placeholder(self) -> None:
        fig = dashboard_charts.usage_over_time([])
        self.assertEqual(len(fig.data), 0)
        self.assertGreaterEqual(len(fig.layout.annotations), 1)
        # Empty cards must still pin the hero-chart height; without it
        # a "no events" state collapses back to Plotly's 450px default
        # and dwarfs the surrounding KPI strip.
        self.assertEqual(fig.layout.height, _HERO_HEIGHT)

    def test_drawn_chart_pins_the_hero_height(self) -> None:
        # The height the panel above the KPI strip is laid out around, on the
        # path that draws bands rather than the placeholder.
        points = [
            TimeSeriesPoint(
                day=_DAY1,
                event=EVENT_AGENT_EXIT,
                count=1,
                cost_usd=1.0,
                input_tokens=10,
                output_tokens=10,
            ),
        ]
        fig = dashboard_charts.usage_over_time(points)
        self.assertEqual(fig.layout.height, _HERO_HEIGHT)
