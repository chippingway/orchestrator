# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The Plotly configuration every figure on the page is handed."""
from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import render_config
from tests.observability.observability_test_support import (
    _imported_orchestrator_modules,
)


_OWNER = "orchestrator.observability.dashboard.render_config"

_MODEBAR_KEY = "displayModeBar"

# What a fresh import of the owner may plant: itself, and the packages it is
# reached through. Configuration is data, so a caller that needs only the
# switch must not pay for a read, a driver, or a figure builder.
_PACKAGE_CHAIN = frozenset((
    "orchestrator",
    "orchestrator._package_exports",
    "orchestrator.observability",
    "orchestrator.observability.dashboard",
    _OWNER,
))


class ModebarTest(unittest.TestCase):
    """The hover toolbar is off, and nothing else is configured."""

    def test_the_modebar_is_switched_off(self) -> None:
        self.assertIs(render_config.PLOTLY_CONFIG[_MODEBAR_KEY], False)

    def test_the_switch_is_the_whole_configuration(self) -> None:
        # Every other Plotly default is Plotly's to pick, so a second key here
        # is a decision the page would be making for every panel at once.
        self.assertEqual(tuple(render_config.PLOTLY_CONFIG), (_MODEBAR_KEY,))


class SharedConfigTest(unittest.TestCase):
    """One panel's configuration cannot become the next panel's."""

    def test_the_published_mapping_is_read_only(self) -> None:
        with self.assertRaises(TypeError):
            render_config.PLOTLY_CONFIG[_MODEBAR_KEY] = True

    def test_a_caller_copy_leaves_the_default_alone(self) -> None:
        # Every call site hands Plotly a plain-dict copy, since the proxy is
        # not JSON-serializable.
        handed = dict(render_config.PLOTLY_CONFIG)
        handed[_MODEBAR_KEY] = True
        self.assertIs(render_config.PLOTLY_CONFIG[_MODEBAR_KEY], False)


class ImportCostTest(unittest.TestCase):
    """Reading the switch costs nothing else under the package."""

    def test_it_plants_no_other_owner(self) -> None:
        self.assertEqual(_imported_orchestrator_modules(_OWNER), _PACKAGE_CHAIN)


if __name__ == "__main__":
    unittest.main()
