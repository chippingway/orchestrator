# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat chart modules still answer for once the owners hold it."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType, ModuleType

_BASE_SITE = "orchestrator.dashboard_charts_base"

_COST_LAYOUT_SITE = "orchestrator._dashboard_cost_layout"

_COST_RANKING_SITE = "orchestrator._dashboard_cost_horizontal"

_COST_STAGE_SITE = "orchestrator._dashboard_cost_stage"

_HEATMAP_SITE = "orchestrator.dashboard_charts_heatmap"

_THROUGHPUT_SITE = "orchestrator.dashboard_charts_throughput"

_USAGE_DATA_SITE = "orchestrator._dashboard_usage_data"

_USAGE_MODELS_SITE = "orchestrator._dashboard_usage_models"

_USAGE_AXIS_SITE = "orchestrator._dashboard_usage_axis"

_USAGE_TRACES_SITE = "orchestrator._dashboard_usage_traces"

_USAGE_CHART_SITE = "orchestrator._dashboard_usage_chart"

_USAGE_PUBLIC_SITE = "orchestrator.dashboard_charts_usage"

_PACKAGE = "orchestrator.observability.dashboard.charts"

_COST_LAYOUT = f"{_PACKAGE}.cost_layout"

_COST_RANKING = f"{_PACKAGE}.cost_horizontal"

_COST_STAGE = f"{_PACKAGE}.cost_stage"

_HEATMAP = f"{_PACKAGE}.heatmap"

_PRIMITIVES = f"{_PACKAGE}.primitives"

_THROUGHPUT = f"{_PACKAGE}.throughput"

_USAGE = f"{_PACKAGE}.usage"

_USAGE_AXIS = f"{_PACKAGE}.usage_axis"

_USAGE_BANDS = f"{_PACKAGE}.usage_bands"

_USAGE_SERIES = f"{_PACKAGE}.usage_series"

_USAGE_TRACES = f"{_PACKAGE}.usage_traces"

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

# The frame the three horizontal cost families share. The generic ranking, the
# per-stage split, and the per-review-round split each reach it through this
# site, so a copy here is how one of them would end up gutter'd or sized unlike
# the two beside it.
_FORWARDED_COST_LAYOUT = (
    ("HORIZONTAL_BAR_MARGIN", _COST_LAYOUT, "HORIZONTAL_BAR_MARGIN"),
    ("_CostBarTrace", _COST_LAYOUT, "CostBarTrace"),
    ("_HorizontalCostLayout", _COST_LAYOUT, "HorizontalCostLayout"),
    (
        "_apply_horizontal_cost_layout",
        _COST_LAYOUT,
        "apply_horizontal_cost_layout",
    ),
    ("_cost_bar_trace", _COST_LAYOUT, "cost_bar_trace"),
)

# The generic ranking, reached through its own site by the cost hub and by the
# per-repository adapter that draws its rows through it. The pinned signature is
# listed beside the builder because that is the call shape both of them are
# written against: a second `Signature` here would let the two disagree about
# what `items` is spelled.
_FORWARDED_COST_RANKING = (
    ("DEFAULT_CHART_HEIGHT", _COST_RANKING, "DEFAULT_CHART_HEIGHT"),
    ("_HORIZONTAL_BAR_SIGNATURE", _COST_RANKING, "HORIZONTAL_BAR_SIGNATURE"),
    ("_HorizontalBarRequest", _COST_RANKING, "HorizontalBarRequest"),
    ("_HorizontalBars", _COST_RANKING, "HorizontalBars"),
    ("_cost_item_sort_key", _COST_RANKING, "cost_item_sort_key"),
    ("_horizontal_bars_data", _COST_RANKING, "horizontal_bars_data"),
    ("_reverse_horizontal_bars", _COST_RANKING, "reverse_horizontal_bars"),
    ("cost_horizontal_bars", _COST_RANKING, "cost_horizontal_bars"),
)

# The per-stage split, reached through its own site by the cost hub and by the
# per-review-round leaf that tints its own cache halves with the shading listed
# here. A second lightening factor or hex base here is how a cache segment on
# one cost panel would end up a different shade from the one beside it.
_FORWARDED_COST_STAGE = (
    ("CACHE_LIGHTEN", _COST_STAGE, "CACHE_LIGHTEN"),
    ("HEX_BASE", _COST_STAGE, "HEX_BASE"),
    ("_StageCostBars", _COST_STAGE, "StageCostBars"),
    ("_lighten_hex", _COST_STAGE, "lighten_hex"),
    ("_reverse_stage_cost_bars", _COST_STAGE, "reverse_stage_cost_bars"),
    ("_stage_cost_bars", _COST_STAGE, "stage_cost_bars"),
    ("_stage_cost_sort_key", _COST_STAGE, "stage_cost_sort_key"),
    ("_stage_no_cache_cost", _COST_STAGE, "stage_no_cache_cost"),
    ("cost_by_stage", _COST_STAGE, "cost_by_stage"),
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

# The step count and pinned height the hero panel is drawn at, the rounding
# each axis maximum comes off, and the layout the two scales are assembled in.
# A layout built here and one built off the owner have to be the same callable:
# the range a stack is drawn against and the range its axis is labelled from
# are one decision, and a copy is where the ticks and the bands would part.
_FORWARDED_USAGE_AXIS = (
    ("USAGE_CHART_HEIGHT", _USAGE_AXIS, "USAGE_CHART_HEIGHT"),
    ("USAGE_GRID_STEPS", _USAGE_AXIS, "USAGE_GRID_STEPS"),
    ("_nice_axis_max", _USAGE_AXIS, "nice_axis_max"),
    ("_usage_axis_ranges", _USAGE_AXIS, "usage_axis_ranges"),
    ("_usage_layout", _USAGE_AXIS, "usage_layout"),
)

# The shaping that decides whether a window has a chart at all, the band a
# stack is added one of at a time, the two modes it is stacked in, and the cost
# line overlaid on it -- down to the layout key a trace's color is set under, so
# the site publishes what it always did rather than the part of it that reads
# like a behavior.
_FORWARDED_USAGE_TRACES = (
    ("_COLOR_KEY", _USAGE_TRACES, "_COLOR_KEY"),
    ("_add_backend_usage_traces", _USAGE_TRACES, "add_backend_usage_traces"),
    ("_add_token_stack_trace", _USAGE_TRACES, "add_token_stack_trace"),
    (
        "_add_token_type_usage_traces",
        _USAGE_TRACES,
        "add_token_type_usage_traces",
    ),
    ("_add_usage_cost_trace", _USAGE_TRACES, "add_usage_cost_trace"),
    ("_add_usage_stack_traces", _USAGE_TRACES, "add_usage_stack_traces"),
    ("_prepare_usage_data", _USAGE_TRACES, "prepare_usage_data"),
)

# The two builders keep their own spelling at both usage sites, so the name a
# caller reads them off and the name the owner defines them under are one.
_BACKEND_PER_DAY = "backend_per_day"

_USAGE_OVER_TIME = "usage_over_time"

# The hero figure and the stub beside it, under the names the public usage
# surface reaches them by. The widget pipeline draws the panel with the object
# behind this site, so a copy here would be a chart an operator reads that no
# fix under the owner reaches.
_FORWARDED_USAGE_CHART = (
    (_BACKEND_PER_DAY, _USAGE, _BACKEND_PER_DAY),
    (_USAGE_OVER_TIME, _USAGE, _USAGE_OVER_TIME),
)

# The whole usage family under the spellings the stable surface publishes: the
# two builders, and beneath them the bands, shapes, axes, and traces they are
# assembled out of. This is the site `orchestrator.dashboard_charts`
# re-exports the family through, so every name here has to be the owner's own
# object rather than one this site defined.
_FORWARDED_USAGE_PUBLIC = (
    ("_CACHE", _USAGE_BANDS, "CACHE_BAND"),
    ("_COST", _USAGE_BANDS, "COST_BAND"),
    ("_DailyTokenValues", _USAGE_BANDS, "DailyTokenValues"),
    ("_INPUT", _USAGE_BANDS, "INPUT_BAND"),
    ("_OUTPUT", _USAGE_BANDS, "OUTPUT_BAND"),
    ("_USAGE_GRID_STEPS", _USAGE_AXIS, "USAGE_GRID_STEPS"),
    ("_UsageAxisRanges", _USAGE_SERIES, "UsageAxisRanges"),
    ("_UsageChartData", _USAGE_SERIES, "UsageChartData"),
    (
        "_add_backend_usage_traces",
        _USAGE_TRACES,
        "add_backend_usage_traces",
    ),
    ("_add_token_stack_trace", _USAGE_TRACES, "add_token_stack_trace"),
    (
        "_add_token_type_usage_traces",
        _USAGE_TRACES,
        "add_token_type_usage_traces",
    ),
    ("_add_usage_cost_trace", _USAGE_TRACES, "add_usage_cost_trace"),
    ("_add_usage_stack_traces", _USAGE_TRACES, "add_usage_stack_traces"),
    ("_backend_names", _USAGE_SERIES, "backend_names"),
    ("_daily_token_total", _USAGE_BANDS, "daily_token_total"),
    ("_date_axis", _USAGE_SERIES, "date_axis"),
    ("_empty_token_bucket", _USAGE_BANDS, "empty_token_bucket"),
    ("_ensure_backend_days", _USAGE_SERIES, "ensure_backend_days"),
    ("_nice_axis_max", _USAGE_AXIS, "nice_axis_max"),
    ("_prepare_usage_data", _USAGE_TRACES, "prepare_usage_data"),
    ("_roll_up_time_series", _USAGE_BANDS, "roll_up_time_series"),
    ("_usage_axis_ranges", _USAGE_AXIS, "usage_axis_ranges"),
    ("_usage_layout", _USAGE_AXIS, "usage_layout"),
    ("_usage_stack_totals", _USAGE_SERIES, "usage_stack_totals"),
    (_BACKEND_PER_DAY, _USAGE, _BACKEND_PER_DAY),
    (_USAGE_OVER_TIME, _USAGE, _USAGE_OVER_TIME),
)

# The flat modules a caller reaches one of these owners through, and what each
# name they publish resolves to.
_FORWARDED_MODULES = MappingProxyType({
    _BASE_SITE: _FORWARDED_PRIMITIVES,
    _COST_LAYOUT_SITE: _FORWARDED_COST_LAYOUT,
    _COST_RANKING_SITE: _FORWARDED_COST_RANKING,
    _COST_STAGE_SITE: _FORWARDED_COST_STAGE,
    _HEATMAP_SITE: _FORWARDED_HEATMAP,
    _THROUGHPUT_SITE: _FORWARDED_THROUGHPUT,
    _USAGE_AXIS_SITE: _FORWARDED_USAGE_AXIS,
    _USAGE_CHART_SITE: _FORWARDED_USAGE_CHART,
    _USAGE_DATA_SITE: _FORWARDED_USAGE_DATA,
    _USAGE_MODELS_SITE: _FORWARDED_USAGE_MODELS,
    _USAGE_PUBLIC_SITE: _FORWARDED_USAGE_PUBLIC,
    _USAGE_TRACES_SITE: _FORWARDED_USAGE_TRACES,
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
        # What keeps the forwarding thin: a second primitive, frame, ranking,
        # grid, strip, or band here would be an implementation the check above
        # cannot see, because it only compares the names the module was asked
        # for.
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
