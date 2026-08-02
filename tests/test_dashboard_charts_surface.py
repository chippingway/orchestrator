# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Dashboard chart leaf import and facade identity tests."""

import importlib


import os


import subprocess


import sys


import unittest


from pathlib import Path


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


_BASE_LEAF = "orchestrator.dashboard_charts_base"


_COST_LEAF = "orchestrator.dashboard_charts_cost"


_USAGE_LEAF = "orchestrator.dashboard_charts_usage"


_USAGE_OWNER = "orchestrator.observability.dashboard.charts.usage"


_HEATMAP_LEAF = "orchestrator.dashboard_charts_heatmap"


_HEATMAP_OWNER = "orchestrator.observability.dashboard.charts.heatmap"


_COST_RANKING_OWNER = "orchestrator.observability.dashboard.charts.cost_horizontal"


_COST_STAGE_OWNER = "orchestrator.observability.dashboard.charts.cost_stage"


_THROUGHPUT_LEAF = "orchestrator.dashboard_charts_throughput"


_THROUGHPUT_OWNER = "orchestrator.observability.dashboard.charts.throughput"


_CHART_LEAVES = (
    _BASE_LEAF,
    _COST_LEAF,
    _USAGE_LEAF,
    _HEATMAP_LEAF,
    _THROUGHPUT_LEAF,
)


_REPO_ROOT = str(Path(__file__).resolve().parents[1])


# Each public builder and the module that defines it. The per-repository and
# per-review-round adapters are still on a flat leaf and are defined there; the
# generic cost ranking, the per-stage split, the heatmap, the throughput strip,
# and the usage builders are defined by their owners under `observability`, and
# the flat leaf named for each forwards that same object. A builder an owner
# defines is also one no leaf may stamp with
# `preserve_defining_module`, since that stamp mutates the object and would
# rewrite the owner's own function.
_BUILDER_HOMES = (
    ("cost_horizontal_bars", _COST_RANKING_OWNER),
    ("cost_by_repo", _COST_LEAF),
    ("cost_by_stage", _COST_STAGE_OWNER),
    ("cost_by_review_round", _COST_LEAF),
    ("usage_over_time", _USAGE_OWNER),
    ("backend_per_day", _USAGE_OWNER),
    ("hour_weekday_heatmap", _HEATMAP_OWNER),
    ("done_per_day_bars", _THROUGHPUT_OWNER),
)


@unittest.skipUnless(HAS_PLOTLY, _SKIP_REASON)
class DirectLeafImportTest(unittest.TestCase):
    """Every chart leaf imports cleanly in a fresh process, not only when
    `dashboard_charts` is imported first.

    `dashboard_charts` is a compatibility hub that re-exports each family's
    builders, and every chart module takes its shared low-level primitives
    from `dashboard_charts_base`. A direct `import` of any leaf must therefore
    resolve without a partially-initialized-module circular import. A
    subprocess gives the clean import graph the in-process test session --
    which has already imported `dashboard_charts` at collection -- cannot.
    """

    def test_each_leaf_imports_standalone(self) -> None:
        for module in _CHART_LEAVES:
            with self.subTest(module=module):
                self._assert_imports_clean(module)

    def _assert_imports_clean(self, module: str) -> None:
        completed = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=_REPO_ROOT,
            env={
                **os.environ,
                "ORCHESTRATOR_SKIP_DOTENV": "1",
                "ORCHESTRATOR_TOKEN_FILE": "/tmp/agent-orchestrator-token-missing",
            },
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"clean-process `import {module}` failed:\n{completed.stderr}",
        )


@unittest.skipUnless(HAS_PLOTLY, _SKIP_REASON)
class ChartHubExtractionTest(unittest.TestCase):
    """Each chart family's public builders live in one focused module, and
    the `orchestrator.dashboard_charts` hub re-exports each under its original
    name so `dashboard_charts.<builder>` (the widget pipeline and these tests
    reach it) keeps resolving to the same object.
    """

    def test_builders_defined_in_their_home(self) -> None:
        for name, module_name in _BUILDER_HOMES:
            with self.subTest(builder=name):
                home = importlib.import_module(module_name)
                self.assertEqual(getattr(home, name).__module__, module_name)

    def test_hub_reexports_the_home_objects(self) -> None:
        from orchestrator import dashboard_charts

        for name, module_name in _BUILDER_HOMES:
            with self.subTest(builder=name):
                home = importlib.import_module(module_name)
                self.assertIs(getattr(dashboard_charts, name), getattr(home, name))
