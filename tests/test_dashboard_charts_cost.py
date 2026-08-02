# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard per-stage cost chart tests."""

import importlib


import unittest

_CACHE_PER_STAGE_COUNT = 20
_CACHE_PER_STAGE_TOTAL_COST_U = 12.0
_CACHE_PER_STAGE_CACHE_COST_U = 9.0
_CACHE_PER_STAGE_NO_CACHE_COS = 3.0
_CACHE_PER_STAGE_TOTA_SECONDARY = 4.0
_LIGHTER_STAGE_COLOR_TOTAL_CO = 10.0
_LIGHTER_STAGE_COLOR_CACHE_CO = 6.0
_LIGHTER_STAGE_COLOR_NO_CACHE = 4.0
_FULL_TOKEN_TOTAL_TOTAL_COST = 7.5
_RUNS_NOT_EVENTS_COUNT = 20
_RUNS_NOT_EVENTS_TOTAL_COST_U = 12.0
_RUNS_NOT_EVENTS_CACHE_COST_U = 9.0
_RUNS_NOT_EVENTS_NO_CACHE_COS = 3.0


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


STAGE_IMPLEMENTING = "implementing"


STAGE_VALIDATING = "validating"


TRACE_CACHE = "Cache"


RGBA_PREFIX = "rgba("


EXPECTED_RGBA_MESSAGE = "expected rgba() cache shade, got "


_PLACEHOLDER_HEIGHT = 120


@unittest.skipUnless(HAS_PLOTLY, _SKIP_REASON)
class CostByStageTest(unittest.TestCase):
    def test_stacks_no_cache_and_cache_per_stage(self) -> None:
        # Each stage splits into (no-cache portion, cache portion).
        # The read model guarantees no_cache + cache == total cost,
        # so the stacked segments add back to the per-stage total.
        rows = [
            StageBreakdown(
                stage=STAGE_IMPLEMENTING,
                count=_CACHE_PER_STAGE_COUNT,
                total_cost_usd=_CACHE_PER_STAGE_TOTAL_COST_U,
                runs=8,
                cache_cost_usd=_CACHE_PER_STAGE_CACHE_COST_U,
                no_cache_cost_usd=_CACHE_PER_STAGE_NO_CACHE_COS,
            ),
            StageBreakdown(
                stage=STAGE_VALIDATING,
                count=5,
                total_cost_usd=_CACHE_PER_STAGE_TOTA_SECONDARY,
                runs=3,
                cache_cost_usd=1.0,
                no_cache_cost_usd=_CACHE_PER_STAGE_NO_CACHE_COS,
            ),
        ]
        fig = dashboard_charts.cost_by_stage(rows)
        no_cache_trace, cache_trace = fig.data
        # Two traces (no-cache base, cache outer), two bars per trace
        # (one per stage). No-cache is added first so cache stacks
        # outward; the chart stacks under `barmode="stack"`.
        self.assertEqual(len(fig.data), 2)
        self.assertEqual([trace.name for trace in fig.data], ["No cache", TRACE_CACHE])
        self.assertEqual(fig.layout.barmode, "stack")
        # Two bars per trace: one per stage.
        self.assertEqual(len(no_cache_trace.y), 2)
        self.assertEqual(len(cache_trace.y), 2)
        self._assert_stage_bars(no_cache_trace, cache_trace)

    def test_cache_segment_uses_lighter_stage_color(self) -> None:
        # Cache and no-cache must stay visibly paired by stage, so the
        # cache segment is a translucent shade of the stage's base
        # color rather than a separate palette.
        rows = [
            StageBreakdown(
                stage=STAGE_IMPLEMENTING,
                count=10,
                total_cost_usd=_LIGHTER_STAGE_COLOR_TOTAL_CO,
                runs=4,
                cache_cost_usd=_LIGHTER_STAGE_COLOR_CACHE_CO,
                no_cache_cost_usd=_LIGHTER_STAGE_COLOR_NO_CACHE,
            ),
        ]
        fig = dashboard_charts.cost_by_stage(rows)
        stage_color = theme.color_for(
            STAGE_IMPLEMENTING,
            explicit=theme.STAGE_COLORS,
        )
        base_colors, cache_colors = [trace.marker.color for trace in fig.data]
        # No-cache uses the canonical stage color verbatim.
        self.assertEqual(base_colors[0], stage_color)
        # Cache uses an rgba() shade of the same color.
        self.assertTrue(
            cache_colors[0].startswith(RGBA_PREFIX),
            "{0}{1}".format(EXPECTED_RGBA_MESSAGE, cache_colors[0]),
        )

    def test_legacy_rows_plot_full_token_total(self) -> None:
        # Fixtures predating the cache-split read model leave
        # `cache_cost_usd` / `no_cache_cost_usd` at the dataclass
        # default of 0.0; falling through would render an empty bar.
        # The chart falls back to plotting the full total as no-cache
        # so the bar length still reads correctly.
        rows = [
            StageBreakdown(
                stage=STAGE_IMPLEMENTING,
                count=10,
                total_cost_usd=_FULL_TOKEN_TOTAL_TOTAL_COST,
                runs=3,
            ),
        ]
        fig = dashboard_charts.cost_by_stage(rows)
        no_cache_trace, cache_trace = fig.data
        self.assertEqual(list(no_cache_trace.x), [7.5])
        self.assertEqual(list(cache_trace.x), [float()])

    def test_sub_line_labels_runs_not_events(self) -> None:
        # The standalone mock aggregates per-agent-run records and
        # labels the sub-line "runs"; we mirror that by reading
        # `StageBreakdown.runs` (the agent-exit subset of `.count`)
        # so a stage with 20 events but only 8 agent runs reports
        # "8 runs", not "20 events".
        rows = [
            StageBreakdown(
                stage=STAGE_IMPLEMENTING,
                count=_RUNS_NOT_EVENTS_COUNT,
                total_cost_usd=_RUNS_NOT_EVENTS_TOTAL_COST_U,
                runs=8,
                cache_cost_usd=_RUNS_NOT_EVENTS_CACHE_COST_U,
                no_cache_cost_usd=_RUNS_NOT_EVENTS_NO_CACHE_COS,
            ),
        ]
        fig = dashboard_charts.cost_by_stage(rows)
        joined = " ".join(fig.data[0].y)
        self.assertIn("8 runs", joined)
        self.assertNotIn("events", joined)

    def test_empty_renders_placeholder(self) -> None:
        fig = dashboard_charts.cost_by_stage([])
        self.assertGreaterEqual(len(fig.layout.annotations), 1)
        self.assertEqual(fig.layout.height, _PLACEHOLDER_HEIGHT)

    def _assert_stage_bars(self, no_cache_trace, cache_trace) -> None:
        # Each stage label appears on the shared y-axis.
        for stage in (STAGE_IMPLEMENTING, STAGE_VALIDATING):
            self.assertTrue(
                any(stage in label for label in no_cache_trace.y),
                "stage {0!r} missing from y labels".format(stage),
            )
        # Largest total ($12) sits at the top, but Plotly's horizontal
        # bar draws the first y-value at the bottom, so the arrays are
        # reversed to [validating, implementing] render order. No-cache
        # [validating 3, implementing 3]; cache [validating 1,
        # implementing 9].
        self.assertEqual(list(no_cache_trace.x), [3.0, 3.0])
        self.assertEqual(list(cache_trace.x), [1.0, 9.0])
        # Only the outer (cache) trace carries the per-stage dollar text
        # so the label lands once per bar instead of on each segment;
        # totals reversed to [validating $4, implementing $12].
        self.assertEqual(no_cache_trace.text, None)
        self.assertEqual(list(cache_trace.text), ["$4.00", "$12"])
