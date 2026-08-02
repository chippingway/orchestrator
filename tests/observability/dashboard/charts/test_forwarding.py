# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat chart modules still answer for once the owners hold it."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType, ModuleType

_BASE_SITE = "orchestrator.dashboard_charts_base"

_HEATMAP_SITE = "orchestrator.dashboard_charts_heatmap"

_PACKAGE = "orchestrator.observability.dashboard.charts"

_HEATMAP = f"{_PACKAGE}.heatmap"

_PRIMITIVES = f"{_PACKAGE}.primitives"

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

# The flat modules a caller reaches one of these owners through, and what each
# name they publish resolves to.
_FORWARDED_MODULES = MappingProxyType({
    _BASE_SITE: _FORWARDED_PRIMITIVES,
    _HEATMAP_SITE: _FORWARDED_HEATMAP,
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

    def test_neither_defines_anything_of_its_own(self) -> None:
        # What keeps the forwarding thin: an implementation here would be a
        # second primitive or a second grid the check above cannot see,
        # because it only compares the names the module was asked for.
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
