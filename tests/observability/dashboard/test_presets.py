# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The windows the named presets stand for, anchored at the data extent.

The extent-bounded presets anchor at the extent's max date rather than today:
a freshly-deployed Postgres whose latest event is a few days old should still
surface a useful window without the operator flipping to `Custom` and reaching
for a calendar. The page exposes `3D` / `7D` / `All` inline and keeps `Custom`
as the sidebar fallback, which is why that one resolves to no window at all.
"""

from __future__ import annotations

import unittest

from orchestrator.observability.analytics.query.overview_models import DataExtent
from orchestrator.observability.dashboard import windows
from tests.observability.dashboard import dashboard_test_support as fixtures


_UNKNOWN_PRESET = "not-a-preset"


class PresetWindowRangeTest(unittest.TestCase):
    """Each preset spans its own day count back from the extent's max."""

    def test_three_day_preset_anchors_at_max(self) -> None:
        extent = fixtures.data_extent(fixtures.MAY01, fixtures.MAY28)
        window = windows.preset_window(
            windows.PRESET_RECENT_THREE_DAYS, extent,
        )
        # Three days span the max date and the two before it, exclusive end at
        # midnight the day after the max.
        self.assertEqual(window.start.date(), fixtures.MAY26)
        self.assertEqual(window.end.date(), fixtures.MAY29)

    def test_seven_day_preset_anchors_at_max(self) -> None:
        extent = fixtures.data_extent(fixtures.MAY01, fixtures.MAY28)
        window = windows.preset_window(windows.PRESET_RECENT_WEEK, extent)
        self.assertEqual(window.start.date(), fixtures.MAY22)
        self.assertEqual(window.end.date(), fixtures.MAY29)

    def test_seven_day_preset_clamps_to_min(self) -> None:
        # The extent is only three days wide -- "Last 7 days" clamps its start
        # at the extent's min rather than reaching before it.
        extent = fixtures.data_extent(fixtures.MAY26, fixtures.MAY28)
        window = windows.preset_window(windows.PRESET_RECENT_WEEK, extent)
        self.assertEqual(window.start.date(), fixtures.MAY26)
        self.assertEqual(window.end.date(), fixtures.MAY29)

    def test_all_preset_covers_full_extent(self) -> None:
        extent = fixtures.data_extent(fixtures.JAN01, fixtures.MAY28)
        window = windows.preset_window(windows.PRESET_ALL, extent)
        self.assertEqual(window.start.date(), fixtures.JAN01)
        self.assertEqual(window.end.date(), fixtures.MAY29)


class PresetWindowValidationTest(unittest.TestCase):
    """What resolves to no window, and the option vocabulary itself."""

    def test_custom_preset_returns_none(self) -> None:
        # The caller renders a date-range picker when the preset is `Custom`;
        # returning `None` is what lets it branch on a falsy value rather than
        # special-casing the preset string in two places.
        extent = fixtures.data_extent(fixtures.MAY01, fixtures.MAY28)
        self.assertIsNone(windows.preset_window(windows.PRESET_CUSTOM, extent))

    def test_unknown_preset_returns_none(self) -> None:
        extent = fixtures.data_extent(fixtures.MAY01, fixtures.MAY28)
        self.assertIsNone(windows.preset_window(_UNKNOWN_PRESET, extent))

    def test_empty_extent_returns_none(self) -> None:
        self.assertIsNone(
            windows.preset_window(windows.PRESET_RECENT_WEEK, DataExtent()),
        )

    def test_extent_dates_read_the_bounding_days(self) -> None:
        extent = fixtures.data_extent(fixtures.MAY01, fixtures.MAY28)
        self.assertEqual(
            windows.extent_dates(extent), (fixtures.MAY01, fixtures.MAY28),
        )
        self.assertIsNone(windows.extent_dates(DataExtent()))

    def test_preset_options_match_the_page(self) -> None:
        # Pin the inline labels the filter bar exposes (3D / 7D / All) and the
        # full option tuple including the Custom fallback, so a later refactor
        # cannot silently re-introduce a retired preset.
        self.assertEqual(
            windows.PRESET_OPTIONS,
            (
                windows.PRESET_RECENT_THREE_DAYS,
                windows.PRESET_RECENT_WEEK,
                windows.PRESET_ALL,
                windows.PRESET_CUSTOM,
            ),
        )
        self.assertEqual(
            set(windows.PRESET_INLINE_LABELS),
            {
                windows.PRESET_RECENT_THREE_DAYS,
                windows.PRESET_RECENT_WEEK,
                windows.PRESET_ALL,
            },
        )


if __name__ == "__main__":
    unittest.main()
