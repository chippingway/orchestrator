# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The grid the window's hours are read off, and the zone it is read in.

What the section decides is not the figure -- that belongs to the chart owner
-- but the zone every part of the card agrees on: the offset is formatted once
and the same label heads the card and annotates the grid's hour axis, so the
two cannot name different zones over one set of cells.

The selectbox is the other decision, and the cases pin it whole: the options
it offers, the formatter each is written by, the key the picked offset is
remembered under, and the help text saying the offset moves the run listing's
`ts` column as well. Nothing here shifts a timestamp, so that key is what ties
the label to a read already bucketed in the zone it names.

The strings an operator reads -- the card's title, the label over that control,
its help text, and that session key -- are spelled out in the cases rather than
read back off the owner. Comparing a render against the constant it was drawn
from asserts only that one name was used twice, which a rename would satisfy
while moving the card an operator scans for or dropping the zone on the next
rerun.

The chart builder is the section's own module-scope import rather than a
handle it is passed, so a recorder stands in for it under `patch.object` on
this owner -- and the render is driven without a chart handle at all, which is
what says the section reaches the family directly.

The Plotly configuration is likewise reached rather than handed, so a case
patches it on the owner that holds it and drives the render, which is what says
the toolbar decision is resolved at call time rather than captured when this
module was imported.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator.observability.dashboard import (
    activity_panel,
    card_html,
    filters,
    render_config,
)
from orchestrator.observability.dashboard.charts import heatmap
from tests.observability.dashboard.activity_panel_test_support import (
    POINTS,
    ActivityStreamlit,
    record_heatmap,
)

_CHART_BUILDER = "hour_weekday_heatmap"

# An offset either side of UTC, so a case reads a zone the default would not
# have produced.
_EASTERN_OFFSET_HOURS = 7

_WESTERN_OFFSET_HOURS = -5

_TOOLBAR_KEY = "displayModeBar"

# What the card reads as, spelled out here rather than read back off the owner:
# the title an operator scans the page for, the label over the zone control,
# the help text naming the second panel that offset moves, and the session key
# the page reads the picked offset back off at the top of the next rerun. A
# case that took these off the owner would pass through a rename that moved the
# card an operator looks for or dropped the zone on the next pass.
_CARD_TITLE = "When agents run"

_SELECT_LABEL = "Timezone"

_SELECT_HELP = (
    'Shifts heatmap bucketing and the "Recent agent runs" '
    "`ts` column to the selected UTC offset. `ts` is stored in UTC."
)

_SESSION_KEY = "tz_offset_hours"

# The Streamlit options each call carries, named rather than spelled at every
# assertion.
_MARKUP_OPTION = "unsafe_allow_html"

_WIDTH_OPTION = "use_container_width"

_CONFIG_OPTION = "config"


def render_panel(
    tz_offset_choice: int = _EASTERN_OFFSET_HOURS,
) -> ActivityStreamlit:
    """Draw the whole card for one offset onto a fake page."""
    page = ActivityStreamlit()
    with patch.object(activity_panel, _CHART_BUILDER, record_heatmap):
        activity_panel.render_activity_heatmap(
            st=page,
            heatmap_rows=POINTS,
            tz_offset_choice=tz_offset_choice,
        )
    return page


class ChartBindingTest(unittest.TestCase):
    """The grid is the chart owner's own builder, not a handed-in hub."""

    def test_the_figure_is_bound_to_its_family(self) -> None:
        # A section is the card and the figure inside it together. Reaching the
        # builder through a handle the caller passed down would let this grid be
        # assembled from a chart family the panels above it were not.
        self.assertIs(
            getattr(activity_panel, _CHART_BUILDER),
            heatmap.hour_weekday_heatmap,
        )


class ActivityRenderOptionTest(unittest.TestCase):
    """Each payload is handed over the way it has to be to be seen."""

    def test_the_card_is_drawn_with_its_outline(self) -> None:
        # The border is what makes the grid, its header, and the zone control
        # above it read as one card rather than as three loose page elements.
        self.assertEqual(render_panel().borders, [True])

    def test_the_header_is_handed_over_as_markup(self) -> None:
        # The header is HTML the markup owner built, so a card handed it
        # without this flag prints the tags an operator was meant to read
        # through.
        drawn = render_panel().markdowns[0]
        self.assertIs(drawn.options[_MARKUP_OPTION], True)

    def test_the_figure_fills_the_card_it_is_in(self) -> None:
        # The grid is sized by the card around it, so a figure left at Plotly's
        # own width would sit in a slot measured for something else.
        drawn = render_panel().figures[0]
        self.assertIs(drawn.options[_WIDTH_OPTION], True)


class ActivityHeatmapTest(unittest.TestCase):
    """One offset names the zone the card and the grid are both read in."""

    def test_the_card_is_headed_by_the_picked_zone(self) -> None:
        page = render_panel()
        self.assertEqual(
            page.markdowns[0].payload,
            card_html.card_header_html(
                _CARD_TITLE, activity_panel.card_subtitle("UTC+7"),
            ),
        )

    def test_the_grid_names_the_same_zone(self) -> None:
        # The cells arrive already bucketed, so the axis label is the only
        # thing saying which zone they are in. Formatting the offset twice is
        # where a header and an axis start naming different ones.
        page = render_panel(_WESTERN_OFFSET_HOURS)
        request = page.figures[0].payload
        self.assertEqual(request.rows, POINTS)
        self.assertEqual(request.tz_label, "UTC-5")
        self.assertIn("UTC-5", page.markdowns[0].payload)

    def test_the_subtitle_crosses_hours_with_days(self) -> None:
        self.assertEqual(
            activity_panel.card_subtitle("UTC"),
            "Token volume by hour (UTC) × weekday",
        )

    def test_the_zone_control_is_drawn_whole(self) -> None:
        # The picked offset is remembered under the key the page reads back at
        # the top of the next rerun to issue the heatmap read, so a widget
        # keyed anywhere else would leave the label naming a zone the cells
        # were never bucketed in. The help text names the run listing too,
        # since the offset is the one selection two panels share.
        drawn = render_panel().selectboxes[0]
        self.assertEqual(drawn.payload, _SELECT_LABEL)
        self.assertEqual(drawn.options["options"], filters.TZ_OFFSET_OPTIONS)
        self.assertIs(drawn.options["format_func"], filters.format_tz_offset)
        self.assertEqual(drawn.options["key"], _SESSION_KEY)
        self.assertEqual(drawn.options["help"], _SELECT_HELP)

    def test_the_toolbar_choice_is_read_at_call(self) -> None:
        # Every figure on the page is drawn under one configuration, and the
        # owner publishes it as a proxy Plotly cannot serialize -- so the grid
        # is handed a plain-dict copy of whatever that owner holds when the
        # section runs.
        sentinel = {_TOOLBAR_KEY: True}
        with patch.object(render_config, "PLOTLY_CONFIG", sentinel):
            handed = render_panel().figures[0].options[_CONFIG_OPTION]
        self.assertEqual(handed, sentinel)
        self.assertIsInstance(handed, dict)
        self.assertIsNot(handed, sentinel)


if __name__ == "__main__":
    unittest.main()
