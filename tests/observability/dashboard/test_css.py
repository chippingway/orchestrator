# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The stylesheet the page injects to draw its own chrome."""
from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import css, palette, tokens


class PageCssShapeTest(unittest.TestCase):
    """`PAGE_CSS` is one string written out verbatim through
    `st.markdown(..., unsafe_allow_html=True)`, so its shape is what decides
    whether the page renders styled at all.
    """

    def test_starts_with_style_tag(self) -> None:
        self.assertTrue(css.PAGE_CSS.lstrip().startswith("<style>"))

    def test_carries_the_class_names_it_renders(self) -> None:
        # A grep is the cheapest gate against a silent rename: the dashboard
        # emits these class names as inline HTML, so a rule renamed on one
        # side leaves the markup on the other unstyled.
        for class_name in (
            ".orch-topbar", ".orch-kpis", ".orch-card", ".orch-insight",
        ):
            with self.subTest(class_name=class_name):
                self.assertIn(class_name, css.PAGE_CSS)

    def test_tokens_reach_the_rendered_string(self) -> None:
        # The CSS variables the chrome reads are interpolated from the palette
        # and geometry owners, so an operator sees the same page color the
        # Plotly figures are built from and the same width the cards are
        # bounded by.
        for token in (
            palette.BACKGROUND,
            palette.ACCENT,
            tokens.CONTENT_MAX_WIDTH,
            tokens.RADIUS,
        ):
            with self.subTest(token=token):
                self.assertIn(token, css.PAGE_CSS)
        # Cards read their corner off the token rather than a literal; the
        # reliability tiles keep their own smaller radius, so the check is
        # anchored on the card rule instead of a bare string search.
        self.assertIn(
            "border-radius: var(--orch-radius) !important", css.PAGE_CSS,
        )

    def test_sticky_chrome_stays_in_the_column(self) -> None:
        # The topbar and filter bar stick to the top of the block container,
        # but `100vw` counts the vertical scrollbar's width and the content
        # area does not -- a full-bleed bar overflows by that much on any page
        # tall enough to scroll, producing a horizontal scrollbar and a sliver
        # of background past its right edge.
        self.assertIn("position: sticky", css.PAGE_CSS)
        self.assertIn("top: 0", css.PAGE_CSS)
        self.assertNotIn("width: 100vw", css.PAGE_CSS)
        self.assertNotIn("calc(50% - 50vw)", css.PAGE_CSS)


class StreamlitChromeTest(unittest.TestCase):
    """The rules that reach into Streamlit's own DOM.

    Each one keys off something the page owns or something stable across
    releases, because a selector aimed at a version-specific testid that
    disappears fails silently: the rule simply stops matching and the surface
    it painted reverts with no error anywhere.
    """

    def test_cards_are_painted_through_the_cardmark(self) -> None:
        # `st.container(border=True)` renders as a `stVerticalBlock` carrying
        # an unstable emotion class, so the page emits a hidden
        # `.orch-cardmark` as each card's first element and the fill matches on
        # that. The direct-child combinator pins the match to the bordered
        # level only -- a bare `:has(.orch-cardmark)` would also paint every
        # ancestor block.
        self.assertIn(".orch-cardmark", css.PAGE_CSS)
        self.assertIn(".orch-filterbar-anchor", css.PAGE_CSS)
        self.assertIn(
            'div[data-testid="stVerticalBlock"]:has(', css.PAGE_CSS,
        )
        self.assertIn(
            '> div[data-testid="stElementContainer"] .orch-cardmark',
            css.PAGE_CSS,
        )
        # Keeps the white fill in the PDF / print export instead of having it
        # stripped.
        self.assertIn("print-color-adjust: exact", css.PAGE_CSS)

    def test_no_rule_keys_off_a_dropped_testid(self) -> None:
        # `stVerticalBlockBorderWrapper` is absent from current Streamlit, so
        # a selector naming it paints nothing -- the cards sit transparent on
        # the gray page and the paired panels mismatch in height. A prose
        # comment may still mention the name for context; a selector may not.
        self.assertNotIn(
            'data-testid="stVerticalBlockBorderWrapper"', css.PAGE_CSS,
        )
        # `:not(:has(...))` is the other selector the embedded browser drops.
        self.assertNotIn(":not(:has(", css.PAGE_CSS)

    def test_top_toolbar_is_clear_and_click_through(self) -> None:
        # Streamlit's toolbar is a `<header>`, so a `div`-scoped rule never
        # matches it and the bar stays opaque, clipping the top of the topbar
        # card. Target it tag-agnostically and make it click-through so it
        # stops intercepting the block beneath, and drop the Deploy button and
        # overflow menu a local dashboard has no use for.
        self.assertIn('[data-testid="stHeader"]', css.PAGE_CSS)
        self.assertIn("pointer-events: none", css.PAGE_CSS)
        self.assertIn('[data-testid="stAppDeployButton"]', css.PAGE_CSS)
        self.assertIn('[data-testid="stMainMenu"]', css.PAGE_CSS)

    def test_equal_height_rows_scoped_to_card_rows(self) -> None:
        # Paired panels line up bottom-to-bottom by stretching each column to
        # the tallest in its row. The rules are scoped to rows that actually
        # carry cards so the filter bar's own inner columns keep their natural
        # layout.
        self.assertIn(
            'div[data-testid="stHorizontalBlock"]:has(.orch-cardmark)',
            css.PAGE_CSS,
        )
        self.assertIn("align-items: stretch", css.PAGE_CSS)

    def test_segmented_control_shows_selection(self) -> None:
        # The date-range preset and hero stack toggle are `st.radio` groups
        # with the dot hidden, so without a rule the active option is
        # indistinguishable from the inactive ones. The radiogroup renders as
        # a chip-colored pill and `:has(input:checked)` lights up the selected
        # label.
        self.assertIn(
            'div[data-testid="stRadio"] > div[role="radiogroup"]',
            css.PAGE_CSS,
        )
        self.assertIn(":has(input:checked)", css.PAGE_CSS)


if __name__ == "__main__":
    unittest.main()
