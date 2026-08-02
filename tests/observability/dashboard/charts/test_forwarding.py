# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat chart modules still answer for once the owners hold it."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType, ModuleType

_BASE_SITE = "orchestrator.dashboard_charts_base"

_HEATMAP_SITE = "orchestrator.dashboard_charts_heatmap"

_THROUGHPUT_SITE = "orchestrator.dashboard_charts_throughput"

_USAGE_DATA_SITE = "orchestrator._dashboard_usage_data"

_USAGE_MODELS_SITE = "orchestrator._dashboard_usage_models"

_PACKAGE = "orchestrator.observability.dashboard.charts"

_HEATMAP = f"{_PACKAGE}.heatmap"

_PRIMITIVES = f"{_PACKAGE}.primitives"

_THROUGHPUT = f"{_PACKAGE}.throughput"

_USAGE_BANDS = f"{_PACKAGE}.usage_bands"

_USAGE_SERIES = f"{_PACKAGE}.usage_series"

# `from __future__ import annotations` opens every module in the repository and
# binds the compiler directive under a public name. It is a compilation
# instruction rather than something these sites answer for, so the surface
# check looks past it.
_FUTURE_DIRECTIVE = "annotations"

# The primitives a caller reaches through the base site, and the owner
# attribute each private spelling resolves to. A placeholder built here and one
# built off the owner have to be the same callable rather than two that agree
# today: the empty state, the bar labels, and the panel height are each one
# decision, and a copy is where a chart family and the owner would start to
# answer differently.
_FORWARDED_PRIMITIVES = (
    ("_HORIZONTAL_BAR_EXTRA_HEIGHT", _PRIMITIVES, "HORIZONTAL_BAR_EXTRA_HEIGHT"),
    ("_HORIZONTAL_BAR_ROW_HEIGHT", _PRIMITIVES, "HORIZONTAL_BAR_ROW_HEIGHT"),
    ("_empty_figure", _PRIMITIVES, "empty_figure"),
    ("_horizontal_legend", _PRIMITIVES, "horizontal_legend"),
    ("_horizontal_panel_height", _PRIMITIVES, "horizontal_panel_height"),
    ("_money_text", _PRIMITIVES, "money_text"),
    ("_monospace_textfont", _PRIMITIVES, "monospace_textfont"),
    ("_reverse_lists", _PRIMITIVES, "reverse_lists"),
    ("_two_line_y_ticks", _PRIMITIVES, "two_line_y_ticks"),
)

# The heatmap the hub re-exports through its own site, with the cells, labels,
# hour span, and layout the figure is assembled from beneath it. The public
# builder is the one the widget pipeline draws the panel with, so a copy here
# would be a grid an operator reads that no fix under the owner reaches.
_FORWARDED_HEATMAP = (
    ("_HOURS_PER_DAY", _HEATMAP, "HOURS_PER_DAY"),
    ("_WEEKDAY_LABELS", _HEATMAP, "WEEKDAY_LABELS"),
    ("_heatmap_layout", _HEATMAP, "heatmap_layout"),
    ("_heatmap_matrix", _HEATMAP, "heatmap_matrix"),
    ("_valid_heatmap_point", _HEATMAP, "valid_heatmap_point"),
    ("hour_weekday_heatmap", _HEATMAP, "hour_weekday_heatmap"),
)

# The strip the hub re-exports through its own site, with the calendar, series,
# and pinned height it is drawn from beneath it. The public builder is the one
# the widget pipeline draws the reliability panel with, so a copy here would be
# a strip an operator reads that no fix under the owner reaches.
_FORWARDED_THROUGHPUT = (
    ("_THROUGHPUT_CHART_HEIGHT", _THROUGHPUT, "THROUGHPUT_CHART_HEIGHT"),
    ("_ThroughputSeries", _THROUGHPUT, "ThroughputSeries"),
    ("_calendar_days", _THROUGHPUT, "calendar_days"),
    ("_throughput_series", _THROUGHPUT, "throughput_series"),
    ("done_per_day_bars", _THROUGHPUT, "done_per_day_bars"),
)

# The bands a day of usage is counted into, the mode its stack is switched
# with, and the roll-up and stack helpers the usage leaves reach across the two
# owners that hold them. A band accumulated under one spelling here and read
# under another beneath the owner is a trace drawn off a total nothing filled.
_FORWARDED_USAGE_DATA = (
    ("BACKEND_MODE", _USAGE_BANDS, "BACKEND_MODE"),
    ("CACHE_BAND", _USAGE_BANDS, "CACHE_BAND"),
    ("COST_BAND", _USAGE_BANDS, "COST_BAND"),
    ("INPUT_BAND", _USAGE_BANDS, "INPUT_BAND"),
    ("OUTPUT_BAND", _USAGE_BANDS, "OUTPUT_BAND"),
    ("_backend_names", _USAGE_SERIES, "backend_names"),
    ("_daily_token_total", _USAGE_BANDS, "daily_token_total"),
    ("_date_axis", _USAGE_SERIES, "date_axis"),
    ("_empty_token_bucket", _USAGE_BANDS, "empty_token_bucket"),
    ("_ensure_backend_days", _USAGE_SERIES, "ensure_backend_days"),
    ("_roll_up_time_series", _USAGE_BANDS, "roll_up_time_series"),
    ("_usage_stack_totals", _USAGE_SERIES, "usage_stack_totals"),
)

# The per-day table's alias and the two frozen shapes a usage figure's days and
# axis maxima travel in. The trace, axis, and figure leaves each name this site,
# so a shape built off a copy is a table one leaf fills and the next cannot read.
_FORWARDED_USAGE_MODELS = (
    ("DailyTokenValues", _USAGE_BANDS, "DailyTokenValues"),
    ("_UsageAxisRanges", _USAGE_SERIES, "UsageAxisRanges"),
    ("_UsageChartData", _USAGE_SERIES, "UsageChartData"),
)

# The flat modules a caller reaches one of these owners through, and what each
# name they publish resolves to.
_FORWARDED_MODULES = MappingProxyType({
    _BASE_SITE: _FORWARDED_PRIMITIVES,
    _HEATMAP_SITE: _FORWARDED_HEATMAP,
    _THROUGHPUT_SITE: _FORWARDED_THROUGHPUT,
    _USAGE_DATA_SITE: _FORWARDED_USAGE_DATA,
    _USAGE_MODELS_SITE: _FORWARDED_USAGE_MODELS,
})


def _published_surface(module: ModuleType) -> frozenset[str]:
    """Names an importer of the historical site can read off it.

    The owner is bound on the site too, by the import that reaches it; what a
    caller reads off the site is everything but that module.
    """
    return frozenset(
        name
        for name, member in module.__dict__.items()
        if not name.startswith("__")
        and name != _FUTURE_DIRECTIVE
        and not isinstance(member, ModuleType)
    )


class ForwardedChartModuleTest(unittest.TestCase):
    """The historical import sites bind the owners' objects, not copies."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        for site, forwarded in _FORWARDED_MODULES.items():
            for name, owner_name, attribute in forwarded:
                with self.subTest(site=site, name=name):
                    self.assertIs(
                        getattr(import_module(site), name),
                        getattr(import_module(owner_name), attribute),
                    )

    def test_the_declared_names_are_the_whole_surface(self) -> None:
        # A name an owner grew but its site never published would leave a
        # chart leaf importing it from two places, and a name published on a
        # site with no owner behind it is an implementation that came back.
        for site, forwarded in _FORWARDED_MODULES.items():
            with self.subTest(site=site):
                self.assertEqual(
                    _published_surface(import_module(site)),
                    frozenset(name for name, _, _ in forwarded),
                )

    def test_no_site_defines_anything_of_its_own(self) -> None:
        # What keeps the forwarding thin: an implementation here would be a
        # second primitive, a second grid, a second strip, or a second band
        # the check above cannot see, because it only compares the names the
        # module was asked for.
        for site in _FORWARDED_MODULES:
            defined = tuple(
                name
                for name, member in import_module(site).__dict__.items()
                if getattr(member, "__module__", None) == site
            )
            with self.subTest(site=site):
                self.assertEqual(defined, ())


if __name__ == "__main__":
    unittest.main()
