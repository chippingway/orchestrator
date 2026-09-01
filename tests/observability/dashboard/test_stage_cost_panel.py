# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The paired lifecycle bars a window's spend is split across.

The cases name what the section decides rather than what the two chart families
draw: the split the columns are laid out in, which axis lands in the wider one,
and -- the reading the whole pairing exists for -- the single height both
figures are pinned to. A bar family sizes itself by its own row count, so the
cases drive windows whose two axes disagree on how many buckets they carry and
read the height each figure was handed straight back off the builder.

Both builders are the section's own module-scope imports rather than a handle
it is passed, so a recorder stands in for them under `patch.object` on this
owner -- which is also what says the section reaches the two cost families
directly, since a stub planted here would not be seen at all if it went on
resolving a builder through something handed in.

The Plotly configuration is likewise reached rather than handed, so a case
patches it on the owner that holds it and drives the render, which is what says
the toolbar decision is resolved at call time rather than captured when this
module was imported.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.observability.analytics.query.cost_models import (
    ReviewRoundBucketRow,
)
from orchestrator.observability.analytics.query.run_models import StageBreakdown
from orchestrator.observability.dashboard import render_config, stage_cost_panel
from orchestrator.observability.dashboard.charts import cost_review, cost_stage
from tests.observability.dashboard.cost_panel_test_support import (
    COLUMN_RATIO,
    LEFT,
    RIGHT,
    CostPanelStreamlit,
    RecordingCharts,
    markup_in,
)

_STAGE_BUILDER = "cost_by_stage"

_ROUND_BUILDER = "cost_by_review_round"

# Two axes that disagree on bucket count, so the shared height is attributable
# to the longer of them rather than to whichever figure was drawn first.
_STAGES = ("implementing", "in_review", "validating")

_ROUNDS = ("0", "1")

# The row count and base the height is built from, restated here so a case
# reads the arithmetic rather than the owner's own expression back.
_ROW_HEIGHT = 40

_BASE_HEIGHT = 80

_TOOLBAR_KEY = "displayModeBar"

# The Streamlit options each call carries, named rather than spelled at every
# assertion.
_MARKUP_OPTION = "unsafe_allow_html"

_WIDTH_OPTION = "use_container_width"

_CONFIG_OPTION = "config"


def stage_rows(*stages: str) -> list[StageBreakdown]:
    """One breakdown row per named workflow stage."""
    return [
        StageBreakdown(stage=stage, count=1, runs=1, total_cost_usd=1.0)
        for stage in stages
    ]


def review_rows(*buckets: str) -> list[ReviewRoundBucketRow]:
    """One development-and-review row per named round bucket."""
    return [
        ReviewRoundBucketRow(bucket=bucket, runs=1, total_cost_usd=1.0)
        for bucket in buckets
    ]


def render_bars(
    stages: tuple[str, ...] = _STAGES,
    rounds: tuple[str, ...] = _ROUNDS,
) -> tuple[CostPanelStreamlit, RecordingCharts]:
    """Draw the whole section for those two axes onto a fake page."""
    page = CostPanelStreamlit()
    charts = RecordingCharts()
    with (
        patch.object(stage_cost_panel, _STAGE_BUILDER, charts.cost_by_stage),
        patch.object(
            stage_cost_panel, _ROUND_BUILDER, charts.cost_by_review_round,
        ),
    ):
        stage_cost_panel.render_stage_review_bars(
            st=page,
            stage_rows=stage_rows(*stages),
            review_round_rows=review_rows(*rounds),
        )
    return page, charts


class PairedBarsHeightTest(unittest.TestCase):
    """One height, measured off whichever axis carried more buckets."""

    def test_the_longer_axis_sets_the_height(self) -> None:
        for stages, rounds, expected_rows in (
            (_STAGES, _ROUNDS, len(_STAGES)),
            (_ROUNDS, _STAGES, len(_STAGES)),
        ):
            with self.subTest(stages=stages, rounds=rounds):
                self.assertEqual(
                    stage_cost_panel.paired_bars_height(
                        stage_rows(*stages), review_rows(*rounds),
                    ),
                    _ROW_HEIGHT * expected_rows + _BASE_HEIGHT,
                )

    def test_an_empty_window_still_gets_a_row(self) -> None:
        # A window neither axis reported on is drawn as the placeholder each
        # family renders instead, and a zero height would collapse the card it
        # is drawn in rather than leaving it the size of the panels beside it.
        self.assertEqual(
            stage_cost_panel.paired_bars_height([], []),
            _ROW_HEIGHT + _BASE_HEIGHT,
        )


class ChartBindingTest(unittest.TestCase):
    """Both figures are the cost owners' own builders, not a handed-in hub."""

    def test_each_axis_is_bound_to_its_own_family(self) -> None:
        # A section is the card and the figure inside it together. Reaching a
        # builder through a handle the caller passed down would let the two
        # halves of one pairing be assembled from different chart families --
        # and a pairing whose whole point is one shared height is exactly the
        # place two families that measure it differently would show.
        self.assertIs(
            getattr(stage_cost_panel, _STAGE_BUILDER),
            cost_stage.cost_by_stage,
        )
        self.assertIs(
            getattr(stage_cost_panel, _ROUND_BUILDER),
            cost_review.cost_by_review_round,
        )


class StageBarsRenderOptionTest(unittest.TestCase):
    """Each payload is handed over the way it has to be to be seen."""

    def test_each_axis_is_drawn_in_a_bordered_card(self) -> None:
        # The outline is what makes each figure read as its own panel rather
        # than as two halves of one strip drawn across the gutter.
        page, _ = render_bars()
        self.assertEqual(page.borders, [(LEFT, True), (RIGHT, True)])

    def test_the_headers_are_handed_over_as_markup(self) -> None:
        # A header is HTML the markup owner built, so a column handed it
        # without this flag prints the tags an operator was meant to read
        # through.
        page, _ = render_bars()
        self.assertEqual(len(page.markdowns), len(page.figures))
        for drawn in page.markdowns:
            with self.subTest(column=drawn.column):
                self.assertIs(drawn.options[_MARKUP_OPTION], True)

    def test_each_figure_fills_the_column_it_is_in(self) -> None:
        # Both panels are sized by the 7:5 split above them, so a figure left
        # at Plotly's own width would sit in a column measured for something
        # else and break the alignment the shared height buys.
        page, _ = render_bars()
        for drawn in page.figures:
            with self.subTest(column=drawn.column):
                self.assertIs(drawn.options[_WIDTH_OPTION], True)


class StageReviewBarsTest(unittest.TestCase):
    """The section lays both figures out and sizes them as one."""

    def test_both_figures_share_one_height(self) -> None:
        _, charts = render_bars()
        heights = {request.height for request in charts.requests}
        self.assertEqual(
            heights, {_ROW_HEIGHT * len(_STAGES) + _BASE_HEIGHT},
        )

    def test_the_stage_axis_takes_the_wider_column(self) -> None:
        page, charts = render_bars()
        self.assertEqual(page.column_request, COLUMN_RATIO)
        drawn_in = {
            drawn.column: drawn.payload.builder for drawn in page.figures
        }
        self.assertEqual(
            drawn_in, {LEFT: _STAGE_BUILDER, RIGHT: _ROUND_BUILDER},
        )
        self.assertEqual(len(charts.requests), len(page.figures))

    def test_each_column_is_headed_by_its_own(self) -> None:
        page, _ = render_bars()
        self.assertIn("Cost by workflow stage", markup_in(page, LEFT))
        self.assertIn(
            "Development and review by round", markup_in(page, RIGHT),
        )

    def test_the_toolbar_choice_is_read_at_call(self) -> None:
        # Every figure on the page is drawn under one configuration, and the
        # owner publishes it as a proxy Plotly cannot serialize -- so each
        # chart is handed a plain-dict copy of whatever that owner holds when
        # the section runs.
        sentinel = {_TOOLBAR_KEY: True}
        with patch.object(render_config, "PLOTLY_CONFIG", sentinel):
            page, _ = render_bars()
        handed = [drawn.options[_CONFIG_OPTION] for drawn in page.figures]
        self.assertEqual(handed, [sentinel, sentinel])
        for config in handed:
            self.assertIsInstance(config, dict)
            self.assertIsNot(config, sentinel)


if __name__ == "__main__":
    unittest.main()
