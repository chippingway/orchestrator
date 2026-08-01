# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, surface, and layering checks for the dashboard owners."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from orchestrator.observability import dashboard as _package
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
)

_PACKAGE = "orchestrator.observability.dashboard"

_CSS_OWNER = "css"

_FORMATTING_OWNER = "formatting"

_LAYOUT_OWNER = "layout"

_PALETTE_OWNER = "palette"

_TOKENS_OWNER = "tokens"

# The declared inventory. A new owner is a deliberate edit here and a paragraph
# in the module map, which is what the inventory check compares the directory
# against.
_OWNERS = (
    _CSS_OWNER,
    _FORMATTING_OWNER,
    _LAYOUT_OWNER,
    _PALETTE_OWNER,
    _TOKENS_OWNER,
)

# What each owner answers for, declared rather than discovered so a second way
# to resolve a color, lay a chart out, or shorten a number is a deliberate edit
# rather than a place two panels could disagree. Three owners report nothing
# because the check reads `__module__`, which only a class or a function
# carries: the palette's whole surface past its resolver is the chrome colors
# and the seven dimension maps, the geometry owner's is its measurements and
# the two font stacks, and the stylesheet owner's is one string.
_SURFACES = MappingProxyType({
    _CSS_OWNER: (),
    _FORMATTING_OWNER: (
        "fmt_money",
        "fmt_money_exact",
        "fmt_num",
        "fmt_tokens",
    ),
    _LAYOUT_OWNER: ("base_layout",),
    _PALETTE_OWNER: ("color_for",),
    _TOKENS_OWNER: (),
})

# The two owners that render a surface out of the tokens rather than declaring
# any: the Plotly defaults every figure is merged with, and the stylesheet the
# chrome around those figures is drawn by.
_RENDERED_SURFACES = (_CSS_OWNER, _LAYOUT_OWNER)

# The historical import site the pages still reach the theme through. No owner
# here may plant it -- that is what keeps the forwarding one-directional and
# the flat module retirable rather than load-bearing.
_COMPATIBILITY_SITE = "orchestrator.dashboard_theme"

_PERMITTED_PREFIXES = ("orchestrator.observability", "orchestrator._package")


def _qualified(owner: str) -> str:
    return f"{_PACKAGE}.{owner}"


def _defined_here(owner: str) -> tuple[str, ...]:
    """Public names the owner defines, as opposed to ones it imported."""
    module = import_module(_qualified(owner))
    return tuple(sorted(
        name
        for name, member in module.__dict__.items()
        if not name.startswith("_")
        and getattr(member, "__module__", None) == module.__name__
    ))


class OwnerInventoryTest(unittest.TestCase):
    """The declared owners are the ones on disk."""

    def test_declared_owners_are_the_ones_on_disk(self) -> None:
        directory = Path(_package.__file__).parent
        found = tuple(sorted(
            module_path.stem
            for module_path in directory.glob("*.py")
            if module_path.stem != "__init__"
        ))
        self.assertEqual(found, tuple(sorted(_OWNERS)))


class PublicSurfaceTest(unittest.TestCase):
    """Each owner answers for a narrow, declared surface."""

    def test_public_names_are_the_declared_ones(self) -> None:
        for owner, surface in _SURFACES.items():
            with self.subTest(owner=owner):
                self.assertEqual(_defined_here(owner), surface)

    def test_no_surface_is_declared_twice(self) -> None:
        # The package initializer is a marker, so a name is reached on the
        # owner that defines it rather than published a second time above it.
        self.assertNotIn("__all__", _package.__dict__)
        for owner in _OWNERS:
            with self.subTest(owner=owner):
                self.assertNotIn(
                    "__all__", import_module(_qualified(owner)).__dict__,
                )


class LayeringTest(unittest.TestCase):
    """The owners reach only siblings, and each rendered surface is built from
    the tokens rather than restating them.
    """

    def test_no_owner_reaches_outside_the_package(self) -> None:
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            for imported in planted:
                with self.subTest(owner=owner, imported=imported):
                    self.assertTrue(
                        imported.startswith(_PERMITTED_PREFIXES)
                        or imported == "orchestrator",
                        f"{owner} reaches {imported}",
                    )

    def test_no_owner_plants_the_historical_site(self) -> None:
        # The sharpest case the check above rejects, named on its own: the
        # flat module a page still imports forwards *to* these owners, so an
        # import back would close the loop and put the compatibility layer
        # inside what rendering a chart costs.
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            with self.subTest(owner=owner):
                self.assertNotIn(_COMPATIBILITY_SITE, planted)

    def test_a_rendered_surface_names_the_tokens(self) -> None:
        # A CSS variable and a figure's gridline are the same value seen twice,
        # so both surfaces have to read it off the owners that hold it: a hue
        # or a radius restated in either place is a page whose chrome and
        # charts drift apart on the next edit.
        for owner in _RENDERED_SURFACES:
            planted = _imported_orchestrator_modules(_qualified(owner))
            for token_owner in (_PALETTE_OWNER, _TOKENS_OWNER):
                with self.subTest(owner=owner, token_owner=token_owner):
                    self.assertIn(_qualified(token_owner), planted)


if __name__ == "__main__":
    unittest.main()
