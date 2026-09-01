# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The window one run of the bar reports over, and how it is picked.

The bar is the one place inclusive dates and half-open windows meet: an
operator reads and types the last day the window covers, while every read
beneath it is bounded `ts < end`. These cases pin that round trip -- what the
preset seeds the pickers with, what the pickers hand back, and the window the
caller leaves with -- plus the two things the bar owes its caller besides that
window: the preset the next rerun reopens on, and the slot the filter line is
written into once the reads come back.
"""

from __future__ import annotations

import unittest
from datetime import timedelta

from orchestrator.observability.analytics.query.overview_models import DataExtent
from orchestrator.observability.dashboard import (
    date_controls,
    date_filter,
    windows,
)
from tests.observability.dashboard import dashboard_test_support as fixtures, date_test_support as fakes

_CARD_MARK = '<div class="orch-cardmark"></div>'


def _render_bar(st: fakes.FakeStreamlit) -> tuple:
    """Draw the bar over a May extent, the way the page draws it."""
    return date_filter.render_date_filter_bar(
        st=st,
        extent=fixtures.data_extent(fixtures.MAY01, fixtures.MAY28),
        extent_min_d=fixtures.MAY01,
        extent_max_d=fixtures.MAY28,
    )


class InitialFilterWindowTest(unittest.TestCase):
    """What the pickers open on before anyone touches them."""

    def test_a_named_preset_opens_on_its_own_window(self) -> None:
        window = date_filter.initial_filter_window(
            windows.PRESET_RECENT_WEEK,
            fixtures.data_extent(fixtures.MAY01, fixtures.MAY28),
            fixtures.MAY01,
            fixtures.MAY28,
        )

        self.assertEqual(window.start.date(), fixtures.MAY22)
        self.assertEqual(window.end.date(), fixtures.MAY29)

    def test_a_windowless_preset_opens_on_the_extent(self) -> None:
        # `Custom` resolves to nothing, and so does any preset on an extent
        # with no rows -- both have to leave the pickers on a real span rather
        # than on an empty bar the operator has to fix before reading anything.
        for extent in (
            fixtures.data_extent(fixtures.MAY01, fixtures.MAY28),
            DataExtent(),
        ):
            with self.subTest(extent=extent):
                window = date_filter.initial_filter_window(
                    windows.PRESET_CUSTOM,
                    extent,
                    fixtures.MAY01,
                    fixtures.MAY28,
                )

                self.assertEqual(window.start.date(), fixtures.MAY01)
                self.assertEqual(window.end.date(), fixtures.MAY29)


class DateInputTest(unittest.TestCase):
    """What the two pickers are seeded and bounded with."""

    def test_pickers_show_the_days_covered(self) -> None:
        # `To` is the last day inside the window, which is one day back from
        # the half-open boundary the reads are bounded by: showing the boundary
        # itself would offer a day the window does not report on.
        st = fakes.FakeStreamlit()
        columns = date_controls.date_filter_columns(st)

        picked = date_filter.render_date_inputs(
            st,
            columns,
            windows.to_window(fixtures.MAY02, fixtures.MAY06),
            fixtures.MAY01,
            fixtures.MAY28,
        )

        self.assertEqual(picked, (fixtures.MAY02, fixtures.MAY06))
        self.assertEqual(
            [
                (region, bounds["label"], bounds["value"])
                for region, bounds in fakes.drawn_as(st, fakes.PICKER)
            ],
            [
                ("start", "From", fixtures.MAY02),
                ("end", "To", fixtures.MAY06),
            ],
        )

    def test_both_pickers_are_clamped_to_the_extent(self) -> None:
        # A window reaching past what the database holds is a panel drawn over
        # days nobody wrote, so the calendar itself refuses them.
        st = fakes.FakeStreamlit()
        columns = date_controls.date_filter_columns(st)

        date_filter.render_date_inputs(
            st,
            columns,
            windows.to_window(fixtures.MAY02, fixtures.MAY06),
            fixtures.MAY01,
            fixtures.MAY28,
        )

        for _, bounds in fakes.drawn_as(st, fakes.PICKER):
            with self.subTest(picker=bounds["label"]):
                self.assertEqual(bounds["min_value"], fixtures.MAY01)
                self.assertEqual(bounds["max_value"], fixtures.MAY28)


class DateFilterBarTest(unittest.TestCase):
    """What one run of the whole bar draws, returns, and leaves behind."""

    def test_a_fresh_session_opens_on_the_default(self) -> None:
        st = fakes.FakeStreamlit()

        window, _ = _render_bar(st)

        self.assertEqual(st.session_state.preset, windows.DEFAULT_PRESET)
        # That default is the seven-day preset, anchored at the extent's max.
        self.assertEqual(window.start.date(), fixtures.MAY22)
        self.assertEqual(window.end.date(), fixtures.MAY29)

    def test_the_clicked_preset_is_written_back(self) -> None:
        # The write-back happens after the bar is drawn, so the radio is
        # offered the choice the session arrived with and the session leaves
        # with the one the operator just made.
        st = fakes.FakeStreamlit(
            preset=windows.PRESET_ALL,
            chosen=windows.PRESET_RECENT_THREE_DAYS,
        )

        window, _ = _render_bar(st)

        offered = fakes.drawn_as(st, fakes.RADIO)[-1][1]
        self.assertEqual(
            offered["options"][offered["index"]], windows.PRESET_ALL,
        )
        self.assertEqual(
            st.session_state.preset, windows.PRESET_RECENT_THREE_DAYS,
        )
        self.assertEqual(window.start.date(), fixtures.MAY26)

    def test_typed_dates_become_the_half_open_window(self) -> None:
        # The pair an operator types is inclusive on both ends; the window the
        # reads are bounded by ends at midnight the day after the second, which
        # is what makes `ts < end` include that day's events.
        st = fakes.FakeStreamlit(picked=(fixtures.MAY03, fixtures.MAY05))

        window, _ = _render_bar(st)

        self.assertEqual(
            window, windows.to_window(fixtures.MAY03, fixtures.MAY05),
        )
        self.assertEqual(window.end - window.start, timedelta(days=3))

    def test_the_bar_hands_back_its_meta_slot(self) -> None:
        # The filter line counts runs, which the first wave of reads has not
        # answered yet, so the trailing slot is held empty and written later.
        st = fakes.FakeStreamlit()

        _, meta_slot = _render_bar(st)

        self.assertEqual(
            fakes.drawn_as(st, fakes.PLACEHOLDER), [("meta", meta_slot)],
        )

    def test_the_bar_is_drawn_as_one_bordered_card(self) -> None:
        # The hidden mark is what the stylesheet selects the card's container
        # by, so it is written inside the border rather than beside it.
        st = fakes.FakeStreamlit()

        _render_bar(st)

        self.assertEqual(st.bordered, [True])
        self.assertIn(
            (fakes.CARD, (_CARD_MARK, True)),
            fakes.drawn_as(st, fakes.MARKDOWN),
        )


if __name__ == "__main__":
    unittest.main()
