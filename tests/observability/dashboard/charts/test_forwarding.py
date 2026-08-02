# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat chart-base module still answers for once the owner holds it."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import ModuleType

_BASE_SITE = "orchestrator.dashboard_charts_base"

_PRIMITIVES = "orchestrator.observability.dashboard.charts.primitives"

# `from __future__ import annotations` opens every module in the repository and
# binds the compiler directive under a public name. It is a compilation
# instruction rather than something this site answers for, so the surface check
# looks past it.
_FUTURE_DIRECTIVE = "annotations"

# The module a caller reaches the primitives through, and the owner attribute
# each private spelling resolves to. A placeholder built here and one built off
# the owner have to be the same callable rather than two that agree today: the
# empty state, the bar labels, and the panel height are each one decision, and a
# copy is where a chart family and the owner would start to answer differently.
_FORWARDED = (
    ("_HORIZONTAL_BAR_EXTRA_HEIGHT", "HORIZONTAL_BAR_EXTRA_HEIGHT"),
    ("_HORIZONTAL_BAR_ROW_HEIGHT", "HORIZONTAL_BAR_ROW_HEIGHT"),
    ("_empty_figure", "empty_figure"),
    ("_horizontal_legend", "horizontal_legend"),
    ("_horizontal_panel_height", "horizontal_panel_height"),
    ("_money_text", "money_text"),
    ("_monospace_textfont", "monospace_textfont"),
    ("_reverse_lists", "reverse_lists"),
    ("_two_line_y_ticks", "two_line_y_ticks"),
)


class ForwardedChartBaseTest(unittest.TestCase):
    """The historical import site binds the owner's objects, not copies."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        site = import_module(_BASE_SITE)
        owner = import_module(_PRIMITIVES)
        for name, attribute in _FORWARDED:
            with self.subTest(name=name):
                self.assertIs(getattr(site, name), getattr(owner, attribute))

    def test_the_declared_names_are_the_whole_surface(self) -> None:
        # A name the owner grew but this module never published would leave a
        # chart leaf importing it from two places, and a name published here
        # with no owner behind it is an implementation that came back.
        # The owner is bound here too, by the import that reaches it; what a
        # caller reads off this site is everything but that module.
        site = import_module(_BASE_SITE)
        published = frozenset(
            name
            for name, member in site.__dict__.items()
            if not name.startswith("__")
            and name != _FUTURE_DIRECTIVE
            and not isinstance(member, ModuleType)
        )
        self.assertEqual(published, frozenset(name for name, _ in _FORWARDED))

    def test_it_defines_nothing_of_its_own(self) -> None:
        # What keeps the forwarding thin: an implementation here would be a
        # second set of primitives the check above cannot see, because it only
        # compares the names the module was asked for.
        site = import_module(_BASE_SITE)
        defined = tuple(
            name
            for name, member in site.__dict__.items()
            if getattr(member, "__module__", None) == _BASE_SITE
        )
        self.assertEqual(defined, ())


if __name__ == "__main__":
    unittest.main()
