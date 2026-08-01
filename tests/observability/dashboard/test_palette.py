# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The color a dimension value and the page chrome are drawn in.

Nothing here needs Plotly: the palette is plain data so a caller can read a
color without the optional `dashboard` dependency group installed.
"""
from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import palette

_IMPLEMENTING = "implementing"

# Each map and the values the page is guaranteed to look up in it. A miss is a
# legend entry that falls through to the ordered palette, so two panels
# rendering the same dimension in a different order would color it differently.
# The stage row is the workflow label set live GitHub issues already carry.
_COVERED_KEYS = (
    (palette.EVENT_COLORS, ("stage_enter", "stage_evaluation", "agent_exit")),
    (palette.STAGE_COLORS, (
        "decomposing", "blocked", "ready", "umbrella", "implementing",
        "validating", "documenting", "in_review", "fixing",
        "resolving_conflict", "question", "done", "rejected",
    )),
    (palette.COST_SOURCE_COLORS, (
        "reported", "estimated", "unknown-price", "no-usage",
    )),
    (palette.TOKEN_TYPE_COLORS, ("Input", "Output", "Cache")),
    (palette.BACKEND_COLORS, ("claude", "codex", "unknown")),
    (palette.REVIEW_ROUND_COLORS, ("0", "1", "2", "3-5", "6+")),
)


class ColorForTest(unittest.TestCase):
    """A key resolves the same way every chart asks for it."""

    def test_explicit_palette_wins(self) -> None:
        # An explicit mapping always overrides domain-position lookup, so the
        # stage colors stay stable even if the chart re-orders rows.
        self.assertEqual(
            palette.color_for(
                _IMPLEMENTING,
                [_IMPLEMENTING, "validating"],
                explicit=palette.STAGE_COLORS,
            ),
            palette.STAGE_COLORS[_IMPLEMENTING],
        )

    def test_domain_position_drives_color(self) -> None:
        # Without an explicit mapping, the n-th entry of the domain gets the
        # n-th entry of `CATEGORICAL_PALETTE`. That property is what makes
        # "the same domain in the same order" produce the same colors across
        # chart re-renders.
        domain = ["a", "b", "c"]
        for domain_key, position in (("a", 0), ("b", 1)):
            with self.subTest(domain_key=domain_key):
                self.assertEqual(
                    palette.color_for(domain_key, domain),
                    palette.CATEGORICAL_PALETTE[position],
                )

    def test_a_key_outside_the_domain_gets_one(self) -> None:
        # A domain is offered but the key is not in it, and a key arrives with
        # no domain at all -- both fall through to the hash rather than raise,
        # because a legend entry the read model produced late must still paint.
        for key, domain in (("zzz", ["a", "b"]), ("anything", None)):
            with self.subTest(key=key):
                self.assertIn(
                    palette.color_for(key, domain),
                    palette.CATEGORICAL_PALETTE,
                )


class DimensionMapTest(unittest.TestCase):
    """The categorical maps are a public contract.

    Each one pins a dimension value to a hue so the value reads the same on
    every panel and across sessions; a value the map has dropped is a legend
    that silently recolors itself.
    """

    def test_each_map_covers_the_keys_it_is_read_for(self) -> None:
        for mapping, keys in _COVERED_KEYS:
            for key in keys:
                with self.subTest(key=key):
                    self.assertIn(key, mapping)

    def test_every_color_is_a_hex_string(self) -> None:
        for mapping, _ in _COVERED_KEYS:
            for key, color in mapping.items():
                with self.subTest(key=key):
                    self.assertTrue(color.startswith("#"))


class ChromeColorTest(unittest.TestCase):
    """The chrome colors are the standalone mock's `:root` block verbatim.

    `.streamlit/config.toml` mirrors the same values into Streamlit's `[theme]`,
    so a drift here shows up as a card painted one gray inside a page painted
    another.
    """

    def test_page_chrome_matches_the_mock(self) -> None:
        # Cool-gray page, white cards, dark blue-gray ink, and the softer
        # ink-2 / ink-3 tints a label and a caption are set in.
        self.assertEqual(palette.BACKGROUND, "#f4f5f8")
        self.assertEqual(palette.CARD_BG, "#ffffff")
        self.assertEqual(palette.TEXT, "#1c2030")
        self.assertEqual(palette.MUTED_TEXT, "#565d72")
        self.assertEqual(palette.MUTED_TEXT_SOFT, "#8a90a3")
        self.assertEqual(palette.BORDER, "#e6e8ef")
        self.assertEqual(palette.GRID, "#eef0f5")
        self.assertEqual(palette.SURFACE, "#f0f1f6")


if __name__ == "__main__":
    unittest.main()
