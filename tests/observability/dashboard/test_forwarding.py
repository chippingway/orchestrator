# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat theme module still answers for once the owners hold it."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType

_THEME_FACADE = "orchestrator.dashboard_theme"

# `from __future__ import annotations` opens every module in the repository and
# binds the compiler directive under a public name. It is a compilation
# instruction rather than something the theme answers for, so the surface check
# looks past it.
_FUTURE_DIRECTIVE = "annotations"

_PACKAGE = "orchestrator.observability.dashboard"

_CSS = f"{_PACKAGE}.css"

_FORMATTING = f"{_PACKAGE}.formatting"

_LAYOUT = f"{_PACKAGE}.layout"

_PALETTE = f"{_PACKAGE}.palette"

_TOKENS = f"{_PACKAGE}.tokens"

# Every name a page reaches through `dashboard_theme`, and the owner it now
# resolves to. A color read here and the same color read off its owner have to
# be one object rather than two equal ones: the CSS variable the chrome is
# drawn from and the Plotly attribute a trace is drawn from are the same value
# seen twice, and a copy is where the two would start to disagree.
_FORWARDED = MappingProxyType({
    _PALETTE: (
        "ACCENT",
        "AGENT_ROLE_COLORS",
        "BACKEND_COLORS",
        "BACKGROUND",
        "BORDER",
        "CARD_BG",
        "CATEGORICAL_PALETTE",
        "COST_SOURCE_COLORS",
        "DANGER",
        "EVENT_COLORS",
        "GRID",
        "INK",
        "MUTED_TEXT",
        "MUTED_TEXT_SOFT",
        "NEUTRAL",
        "PRIMARY",
        "REVIEW_ROUND_COLORS",
        "SECONDARY",
        "STAGE_COLORS",
        "SUCCESS",
        "SURFACE",
        "TEXT",
        "TOKEN_TYPE_COLORS",
        "WARNING",
        "color_for",
    ),
    _TOKENS: (
        "CARD_PADDING",
        "CONTENT_MAX_WIDTH",
        "FONT_FAMILY",
        "FONT_SIZE",
        "GRID_GAP",
        "MONO_FONT_FAMILY",
        "RADIUS",
        "TITLE_FONT_SIZE",
        "TOPBAR_STICKY_HEIGHT",
    ),
    _LAYOUT: ("base_layout",),
    _CSS: ("PAGE_CSS",),
    _FORMATTING: (
        "fmt_money",
        "fmt_money_exact",
        "fmt_num",
        "fmt_tokens",
    ),
})


def _facade_surface() -> frozenset[str]:
    """Public names an importer of the historical site can read off it."""
    facade = import_module(_THEME_FACADE)
    return frozenset(
        name
        for name in facade.__dict__
        if not name.startswith("_") and name != _FUTURE_DIRECTIVE
    )


class ForwardedThemeTest(unittest.TestCase):
    """The historical import site binds the owners' objects, not copies."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        facade = import_module(_THEME_FACADE)
        for owner_name, forwarded in _FORWARDED.items():
            owner = import_module(owner_name)
            for name in forwarded:
                with self.subTest(owner=owner_name, name=name):
                    self.assertIs(getattr(facade, name), getattr(owner, name))

    def test_the_declared_names_are_the_whole_surface(self) -> None:
        # A name the owners grew but the flat module never published would
        # leave a page importing it from two places, and a name published here
        # with no owner behind it is an implementation that came back.
        declared = frozenset(
            name for forwarded in _FORWARDED.values() for name in forwarded
        )
        self.assertEqual(_facade_surface(), declared)

    def test_it_defines_nothing_of_its_own(self) -> None:
        # What keeps the forwarding thin: an implementation here would be a
        # second set of tokens the check above cannot see, because it only
        # compares the names the module was asked for.
        facade = import_module(_THEME_FACADE)
        defined = tuple(
            name
            for name, member in facade.__dict__.items()
            if getattr(member, "__module__", None) == _THEME_FACADE
        )
        self.assertEqual(defined, ())


if __name__ == "__main__":
    unittest.main()
