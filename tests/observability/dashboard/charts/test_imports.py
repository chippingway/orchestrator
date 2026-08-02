# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Inventory, surface, and layering checks for the chart owners."""
from __future__ import annotations

import unittest
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from orchestrator.observability.dashboard import charts as _package
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
    _run_import_probe,
)

_DASHBOARD = "orchestrator.observability.dashboard"

_PACKAGE = f"{_DASHBOARD}.charts"

_HEATMAP_OWNER = "heatmap"

_PRIMITIVES_OWNER = "primitives"

# The declared inventory. A new chart family is a deliberate edit here and a
# paragraph in the module map, which is what the inventory check compares the
# directory against.
_OWNERS = (_HEATMAP_OWNER, _PRIMITIVES_OWNER)

# What each owner answers for, declared rather than discovered so a second way
# to say "nothing matches this window", label a bar, size the panel it sits in,
# or bucket a token volume into a weekday cell is a deliberate edit rather than
# a place two chart families could disagree. The two bar-sizing constants and
# the heatmap's weekday labels and hour span are invisible here because the
# check reads `__module__`, which only a class or a function carries.
_SURFACES = MappingProxyType({
    _HEATMAP_OWNER: (
        "heatmap_layout",
        "heatmap_matrix",
        "hour_weekday_heatmap",
        "valid_heatmap_point",
    ),
    _PRIMITIVES_OWNER: (
        "empty_figure",
        "horizontal_legend",
        "horizontal_panel_height",
        "money_text",
        "monospace_textfont",
        "reverse_lists",
        "two_line_y_ticks",
    ),
})

# The historical import sites the chart leaves still reach these owners
# through. No owner here may plant one -- that is what keeps the forwarding
# one-directional and the flat modules retirable rather than load-bearing.
_COMPATIBILITY_SITES = (
    "orchestrator.dashboard_charts_base",
    "orchestrator.dashboard_charts_heatmap",
)

# What an owner here may reach: the theme owners a figure is drawn with, which
# is one package up, the read models whose rows it is drawn from, which are
# under the analytics query owners, and the root package every import plants on
# its way in. A color, a font stack, the layout every figure is merged with,
# and the shape of a row are answers already decided there, so a builder names
# those owners rather than restating a hue, a margin, or a field of its own.
_PERMITTED_PREFIXES = ("orchestrator.observability", "orchestrator._package")

# Plotly ships in the optional `dashboard` dependency group, so a figure is
# built with an import inside the call rather than at module scope. Both the
# package a page reaches these builders through and the owner behind it have to
# stay importable in the default install, which carries neither Plotly nor
# Streamlit -- the tree-wide sweep in `test_optional_dependencies` proves the
# import is refused there, and this probe proves it is not paid for in an
# install that does have the package.
_PLOTLY_PROBE = """
import sys
import {module}
loaded = [name for name in sys.modules if name.split('.')[0] == 'plotly']
sys.exit(', '.join(loaded) if loaded else 0)
"""


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
    """The owners reach only the theme they draw with, and nothing here --
    nor the package a page opens them through -- loads Plotly to be imported.
    """

    def test_no_owner_reaches_outside_observability(self) -> None:
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            for imported in planted:
                with self.subTest(owner=owner, imported=imported):
                    self.assertTrue(
                        imported.startswith(_PERMITTED_PREFIXES)
                        or imported == "orchestrator",
                        f"{owner} reaches {imported}",
                    )

    def test_no_owner_plants_a_historical_site(self) -> None:
        # The sharpest case the check above rejects, named on its own: the
        # flat modules the chart leaves import forward *to* these owners, so
        # an import back would close the loop and leave a direct import of any
        # chart module resolving off a half-initialized one.
        for owner in _OWNERS:
            planted = _imported_orchestrator_modules(_qualified(owner))
            for site in _COMPATIBILITY_SITES:
                with self.subTest(owner=owner, site=site):
                    self.assertNotIn(site, planted)

    def test_no_import_here_loads_plotly(self) -> None:
        for module in (_DASHBOARD, _PACKAGE, *map(_qualified, _OWNERS)):
            completed = _run_import_probe(_PLOTLY_PROBE.format(module=module))
            with self.subTest(module=module):
                self.assertEqual(
                    completed.returncode, 0, msg=completed.stderr,
                )


if __name__ == "__main__":
    unittest.main()
