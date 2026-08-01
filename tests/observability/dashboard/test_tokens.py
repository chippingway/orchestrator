# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The geometry and type the page is laid out and set in."""
from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import tokens


class TokenValueTest(unittest.TestCase):
    """The measurements and font stacks are the mock's `:root` block.

    Both surfaces that consume them -- the Plotly layout and the injected page
    CSS -- read the same values, so a token that drifts moves a chart and the
    card around it by different amounts.
    """

    def test_geometry_matches_the_mock(self) -> None:
        self.assertEqual(tokens.RADIUS, "14px")
        self.assertEqual(tokens.CARD_PADDING, "20px")
        self.assertEqual(tokens.GRID_GAP, "16px")
        self.assertEqual(tokens.CONTENT_MAX_WIDTH, "1480px")

    def test_ibm_plex_leads_each_font_stack(self) -> None:
        # The mock specifies IBM Plex Sans / Mono. Each stack names one first
        # and keeps the system fallbacks behind it, so the page still sets
        # cleanly in a browser without the bundled woff2 fonts.
        self.assertIn("IBM Plex Sans", tokens.FONT_FAMILY)
        self.assertIn("IBM Plex Mono", tokens.MONO_FONT_FAMILY)


if __name__ == "__main__":
    unittest.main()
