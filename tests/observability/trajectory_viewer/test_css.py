# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The stylesheet the viewer adds on top of the chrome both pages share."""
from __future__ import annotations

import re
import unittest

from orchestrator.observability.dashboard import tokens
from orchestrator.observability.trajectory_viewer import css


class ExtraCssShapeTest(unittest.TestCase):
    """`EXTRA_CSS` is one string written out verbatim through
    `st.markdown(..., unsafe_allow_html=True)`, so its shape is what decides
    whether the viewer's own surfaces render styled at all.
    """

    def test_starts_with_style_tag(self) -> None:
        self.assertTrue(css.EXTRA_CSS.lstrip().startswith("<style>"))

    def test_carries_the_class_names_the_page_emits(self) -> None:
        # A grep is the cheapest gate against a silent rename: the builders
        # emit these class names as inline HTML, so a rule renamed on one side
        # leaves the markup on the other unstyled.
        for class_name in (
            ".orch-traj-meta-item",
            ".orch-traj-chip",
            ".orch-traj-table",
            ".orch-traj-badge",
            ".orch-traj-fixture-tag",
            ".orch-traj-turn",
        ):
            with self.subTest(class_name=class_name):
                self.assertIn(class_name, css.EXTRA_CSS)

    def test_only_the_kpi_grid_reaches_shared_chrome(self) -> None:
        # Everything else is scoped to a class this page alone emits, so a
        # rule here cannot repaint the analytics page. `.orch-kpis` is the
        # deliberate exception, and naming it is what keeps a second one from
        # arriving unnoticed.
        reached = sorted(set(re.findall(r"\.orch-[a-z-]+", css.EXTRA_CSS)))
        self.assertEqual(
            [name for name in reached if not name.startswith(".orch-traj-")],
            [".orch-kpis"],
        )


class SharedThemeTest(unittest.TestCase):
    """The viewer is drawn in the type and palette the analytics page is."""

    def test_both_font_stacks_reach_the_sheet(self) -> None:
        # A stack cannot be read out of a CSS variable the shared stylesheet
        # never declared as one, so these are interpolated from the geometry
        # owner rather than restated -- which is what keeps a face changed
        # there moving both pages together.
        self.assertIn(tokens.FONT_FAMILY, css.EXTRA_CSS)
        self.assertIn(tokens.MONO_FONT_FAMILY, css.EXTRA_CSS)

    def test_chrome_colors_read_the_shared_variables(self) -> None:
        # Deliberately *not* interpolated: the chrome's colors arrive as CSS
        # variables the shared stylesheet declares, so a palette edit moves
        # both pages at once.
        for token_name in ("--orch-border", "--orch-card", "--orch-ink"):
            with self.subTest(token_name=token_name):
                self.assertIn(f"var({token_name})", css.EXTRA_CSS)

    def test_only_translucent_washes_are_literal(self) -> None:
        # A variable holds an opaque hex, so a wash under a badge has to be
        # spelled out with its own alpha. That is the one exemption: every
        # other color declaration reads a variable, and a solid literal
        # arriving here would be a shade the shared palette cannot move.
        literal = [
            f"{prop}: {painted}"
            for prop, painted in re.findall(
                r"(background|color|border-color|border):\s*([^;]+);",
                css.EXTRA_CSS,
            )
            if "var(" not in painted and painted != "transparent"
        ]
        self.assertTrue(literal)
        for declaration in literal:
            with self.subTest(declaration=declaration):
                self.assertRegex(declaration, r"rgba\([\d, ]+\.\d+\)$")


class KpiGridTest(unittest.TestCase):
    """The fifth tile this page adds has to survive a narrow viewport."""

    def test_five_tiles_reflow_to_two_columns(self) -> None:
        # Both rules follow the shared stylesheet, so they win the cascade
        # without raising specificity -- but the shared sheet's own reflow is
        # written for four tiles, so the narrow-viewport rule has to be
        # restated here or five would stay across on a phone-width window.
        self.assertIn("repeat(5, 1fr)", css.EXTRA_CSS)
        self.assertIn("@media (max-width: 1080px)", css.EXTRA_CSS)
        self.assertIn("repeat(2, 1fr)", css.EXTRA_CSS)


if __name__ == "__main__":
    unittest.main()
