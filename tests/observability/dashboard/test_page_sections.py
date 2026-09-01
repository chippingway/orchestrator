# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The order the panels under the figures are drawn in, and the whole wave.

The four sections beneath the figure cards are each their own owner and pinned
beside it; what this owner decides is the order and what each is handed. The
cases stub every one of them on the module that holds it -- which is also the
check that the pass names the owners rather than resolving a render off a
facade -- and answer each read with its own key, so a panel handed the wrong
family reads back as the wrong word. The last case is about the two halves
together: the figure cards come first, and the page's whole order stays
readable from one call.
"""

from __future__ import annotations

import unittest
from functools import partial

from orchestrator.observability.dashboard import (
    chart_sections,
    drilldown,
    page_sections,
    page_states,
    recent_runs,
    skill_panel,
)
from tests.observability.dashboard.page_render_test_support import (
    TZ_OFFSET,
    draw_sections,
    loaded,
    modules,
    page,
    section_reads,
)

_SKILL_CARD = "render_skill_adoption"

_RUN_LISTING = "render_recent_runs"

_ISSUE_TRACE = "render_drilldown_view"

_FOOTER = "render_dashboard_footer"

# The four sections under the figure cards, in page order and paired with the
# owner each is stubbed on.
_PAGE_PANELS = (
    (skill_panel, _SKILL_CARD),
    (recent_runs, _RUN_LISTING),
    (drilldown, _ISSUE_TRACE),
    (page_states, _FOOTER),
)

# The three cells the skill card is drawn from, each answering with its own key.
_SKILL_READS = ("skill_adoption_rows", "skill_rows", "skill_matrix_rows")

# The two halves of the second wave, in the order one call draws them.
_CHART_HALF = "render_chart_widgets"

_REMAINING_HALF = "render_remaining_widgets"

_WAVE_PANELS = (
    (chart_sections, _CHART_HALF),
    (page_sections, _REMAINING_HALF),
)


class PageSectionOrderTest(unittest.TestCase):
    """Which panel follows which under the figures, and what each is given."""

    def setUp(self) -> None:
        self.st = object()
        self.frames = object()
        self.page = page()
        drawn, recorder = draw_sections(
            _PAGE_PANELS,
            partial(
                page_sections.render_remaining_widgets,
                modules(self.st, frames=self.frames),
                self.page,
                loaded(section_reads()),
            ),
        )
        self.drawn = drawn
        self.recorder = recorder

    def test_the_panels_follow_in_page_order(self) -> None:
        # The skill card reports what the runs behind the figures were working
        # with, the listing is the rows every reading above was reduced from,
        # the trace is one of those rows opened out, and the footer restates
        # what all of it was measured over -- so it is last.
        self.assertEqual(
            self.drawn, [attribute for _, attribute in _PAGE_PANELS],
        )

    def test_the_skill_card_is_handed_its_three_cells(self) -> None:
        drawn = getattr(self.recorder, _SKILL_CARD).call_args.kwargs

        self.assertIs(drawn["st"], self.st)
        self.assertEqual(
            {name: drawn[name] for name in _SKILL_READS},
            {name: name for name in _SKILL_READS},
        )

    def test_the_listing_gets_the_frame_and_the_zone(self) -> None:
        # It is the one section rendered through pandas, and its timestamps are
        # shifted into the zone the sidebar picked rather than left in UTC.
        drawn = getattr(self.recorder, _RUN_LISTING).call_args.kwargs

        self.assertIs(drawn["pd"], self.frames)
        self.assertEqual(drawn["agent_exits"], "agent_exits")
        self.assertEqual(drawn["tz_offset_choice"], TZ_OFFSET)

    def test_the_trace_and_footer_read_one_filter_set(self) -> None:
        # Both are narrowed by what the controls resolved rather than by
        # anything the reads came back with, so they are handed the page's own
        # filters -- and the footer the window totals beside them.
        traced = getattr(self.recorder, _ISSUE_TRACE).call_args.args
        signed_off = getattr(self.recorder, _FOOTER).call_args.args

        self.assertIs(traced[1], self.page.controls.filters)
        self.assertIs(signed_off[1], self.page.controls.filters)
        self.assertEqual(signed_off[2], "summary")


class RenderDashboardWidgetsTest(unittest.TestCase):
    """The whole second wave in one call, in the order the page draws it."""

    def test_the_figure_cards_come_first(self) -> None:
        # Splitting the order across two calls is what lets a caller draw
        # either half against a stand-in; keeping the pair in one call is what
        # keeps the page's order readable from a single place.
        page_state = page()
        drawn, recorder = draw_sections(
            _WAVE_PANELS,
            partial(
                page_sections.render_dashboard_widgets,
                modules(object()),
                page_state,
                loaded(section_reads()),
            ),
        )

        self.assertEqual(drawn, [_CHART_HALF, _REMAINING_HALF])
        self.assertIs(
            getattr(recorder, _CHART_HALF).call_args.args[1], page_state,
        )
        self.assertEqual(
            getattr(recorder, _CHART_HALF).call_args.args,
            getattr(recorder, _REMAINING_HALF).call_args.args,
        )


if __name__ == "__main__":
    unittest.main()
