# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The slots the filter bar is drawn across, and the presets among them.

The layout is five columns rather than a row of equal ones because each holds a
different widget: the label naming the bar, the preset radio, the two date
pickers, and the room the filter line is written into once the reads come back.
The preset radio is the one widget whose position is state -- it has to reopen
on the choice the session is carrying, and a preset it does not offer has to
land somewhere rather than nowhere.
"""

from __future__ import annotations

import unittest

from orchestrator.observability.dashboard import date_controls, windows
from tests.observability.dashboard import date_test_support as fakes


# The widths and alignment the five slots are laid out at. The bar sits under
# the topbar with each picker's own caption above it, so the row is aligned to
# its bottom edge, and the widest slot is the trailing one the filter line is
# written into.
_SLOT_WIDTHS = (1.0, 1.7, 1.4, 1.4, 3.0)

_SLOT_ALIGNMENT = "bottom"

_UNKNOWN_PRESET = "not-a-preset"


class DateFilterLayoutTest(unittest.TestCase):
    """The row one bar is laid out in, and the label naming it."""

    def test_the_five_slots_are_bound_in_page_order(self) -> None:
        st = fakes.FakeStreamlit()

        columns = date_controls.date_filter_columns(st)

        self.assertEqual(st.column_request, (_SLOT_WIDTHS, _SLOT_ALIGNMENT))
        self.assertEqual(
            (
                columns.label,
                columns.preset,
                columns.start,
                columns.end,
                columns.meta,
            ),
            tuple(st.slots),
        )

    def test_the_label_is_drawn_in_its_own_slot(self) -> None:
        # The anchor is what the sticky chrome measures the bar from, so it is
        # written with the label rather than left to the caller.
        st = fakes.FakeStreamlit()
        columns = date_controls.date_filter_columns(st)

        date_controls.render_date_filter_label(st, columns.label)

        region, request = fakes.drawn_as(st, fakes.MARKDOWN)[-1]
        self.assertEqual(region, "label")
        self.assertIn('class="orch-filterbar-anchor"', request[0])
        self.assertIn(">Date range<", request[0])
        self.assertTrue(request[1])


class PresetChoiceTest(unittest.TestCase):
    """Which presets the bar offers, and where it reopens on each."""

    def test_each_offered_preset_reopens_on_itself(self) -> None:
        for position, preset in enumerate(date_controls.INLINE_PRESETS):
            with self.subTest(preset=preset):
                self.assertEqual(
                    date_controls.preset_radio_index(preset), position,
                )

    def test_an_unoffered_preset_falls_to_the_last(self) -> None:
        # `Custom` is picked in the sidebar and names no window of its own, so
        # the inline row opens on `All` rather than on nothing at all.
        for preset in (windows.PRESET_CUSTOM, _UNKNOWN_PRESET, ""):
            with self.subTest(preset=preset):
                self.assertEqual(
                    date_controls.preset_radio_index(preset),
                    len(date_controls.INLINE_PRESETS) - 1,
                )

    def test_the_radio_offers_three_presets(self) -> None:
        st = fakes.FakeStreamlit(preset=windows.PRESET_RECENT_THREE_DAYS)
        columns = date_controls.date_filter_columns(st)

        chosen = date_controls.render_preset_choice(st, columns.preset)

        region, options = fakes.drawn_as(st, fakes.RADIO)[-1]
        self.assertEqual(region, "preset")
        self.assertEqual(
            options["options"],
            (
                windows.PRESET_RECENT_THREE_DAYS,
                windows.PRESET_RECENT_WEEK,
                windows.PRESET_ALL,
            ),
        )
        self.assertEqual(chosen, windows.PRESET_RECENT_THREE_DAYS)

    def test_the_radio_is_labelled_and_keyed(self) -> None:
        # The inline labels are the window owner's, so the button an operator
        # clicks and the span it stands for cannot be named two ways; the key
        # is what Streamlit stores the widget's own state under across reruns.
        st = fakes.FakeStreamlit(preset=windows.PRESET_ALL)
        columns = date_controls.date_filter_columns(st)

        date_controls.render_preset_choice(st, columns.preset)

        options = fakes.drawn_as(st, fakes.RADIO)[-1][1]
        self.assertEqual(options["index"], len(options["options"]) - 1)
        self.assertEqual(options["key"], "_preset_radio")
        self.assertEqual(
            [options["format_func"](preset) for preset in options["options"]],
            ["3D", "7D", "All"],
        )


if __name__ == "__main__":
    unittest.main()
