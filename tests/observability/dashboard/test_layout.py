# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The Plotly layout every chart on the page is merged with."""
from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import layout, palette


class BaseLayoutTest(unittest.TestCase):
    """The shared layout is plain data a builder can splat.

    Producing it costs no Plotly import, which is what keeps the owners around
    a chart testable in an install without the optional `dashboard` group.
    """

    def test_returns_plain_dict(self) -> None:
        # Chart builders splat the result into `fig.update_layout(**...)`, so
        # any non-dict type would break the call site.
        built = layout.base_layout()
        self.assertIsInstance(built, dict)
        # The plot background is the card surface (white) because every chart
        # renders inside a card.
        self.assertEqual(built["paper_bgcolor"], palette.CARD_BG)
        self.assertEqual(built["plot_bgcolor"], palette.CARD_BG)
        self.assertIn("font", built)
        self.assertNotIn("title", built)

    def test_title_threads_through(self) -> None:
        built = layout.base_layout(title="Hello")
        self.assertEqual(built["title"]["text"], "Hello")
        # The top margin grows when a title is present so the title has room
        # to render above the plot area.
        self.assertGreaterEqual(built["margin"]["t"], 24)


if __name__ == "__main__":
    unittest.main()
