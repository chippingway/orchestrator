# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a page narrows its window by, and the key that reads follow it."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from orchestrator.observability.dashboard import filters, windows
from tests.observability.dashboard import dashboard_test_support as fixtures

# The offset the page opens on. It is documented as UTC+7 rather than merely
# selectable, so it is pinned by value here and is also the eastern offset the
# shift cases are read in.
_DEFAULT_OFFSET_HOURS = 7

_WESTERN_OFFSET_HOURS = -5

_NOON = 12

_SHIFTED_HOUR = 19

_WESTERN_SHIFTED_HOUR = 7

_ISSUE_NUMBER = 42

_NOON_UTC = datetime(
    fixtures.MAY01.year, fixtures.MAY01.month, fixtures.MAY01.day, _NOON,
    tzinfo=UTC,
)

_NOON_NAIVE = _NOON_UTC.replace(tzinfo=None)

_CACHE_REPO = "acme/widgets"

_EVENT_NAMES = ("agent_exit", "stage_enter")

_STAGE_NAMES = ("implementing",)

_OTHER_STAGE = "validating"


class FormatTzOffsetTest(unittest.TestCase):
    """The offset label the sidebar and the heatmap subtitle carry."""

    def test_zero_is_utc(self) -> None:
        self.assertEqual(filters.format_tz_offset(0), "UTC")

    def test_signed_offsets(self) -> None:
        self.assertEqual(
            filters.format_tz_offset(_DEFAULT_OFFSET_HOURS), "UTC+7",
        )
        self.assertEqual(
            filters.format_tz_offset(_WESTERN_OFFSET_HOURS), "UTC-5",
        )

    def test_default_offset_is_plus_seven(self) -> None:
        # The value itself is the contract: a page that opened on any other
        # selectable offset would render every timestamp on the wrong clock
        # while still passing a membership check.
        self.assertEqual(
            filters.DEFAULT_TZ_OFFSET_HOURS, _DEFAULT_OFFSET_HOURS,
        )
        self.assertIn(
            filters.DEFAULT_TZ_OFFSET_HOURS, filters.TZ_OFFSET_OPTIONS,
        )


class ShiftTsTest(unittest.TestCase):
    """A stored UTC timestamp is rendered in the selected wall clock."""

    def test_none_passes_through(self) -> None:
        self.assertIsNone(
            filters.shift_ts(None, timedelta(hours=_DEFAULT_OFFSET_HOURS)),
        )

    def test_aware_ts_converted_to_offset(self) -> None:
        shifted = filters.shift_ts(
            _NOON_UTC, timedelta(hours=_DEFAULT_OFFSET_HOURS),
        )
        self.assertEqual(shifted.hour, _SHIFTED_HOUR)
        self.assertEqual(
            shifted.utcoffset(), timedelta(hours=_DEFAULT_OFFSET_HOURS),
        )

    def test_aware_ts_negative_offset(self) -> None:
        shifted = filters.shift_ts(
            _NOON_UTC, timedelta(hours=_WESTERN_OFFSET_HOURS),
        )
        self.assertEqual(shifted.hour, _WESTERN_SHIFTED_HOUR)
        self.assertEqual(
            shifted.utcoffset(), timedelta(hours=_WESTERN_OFFSET_HOURS),
        )

    def test_naive_ts_shifted_in_place(self) -> None:
        # A naive timestamp carries no zone to convert from, so the offset is
        # added rather than applied -- which keeps a row read back from a
        # driver that dropped the zone on the same clock as its neighbours.
        shifted = filters.shift_ts(
            _NOON_NAIVE, timedelta(hours=_DEFAULT_OFFSET_HOURS),
        )
        self.assertEqual(shifted, _NOON_NAIVE.replace(hour=_SHIFTED_HOUR))


class ParseIssueNumberTest(unittest.TestCase):
    """The free-text issue box accepts `123` and `#123`, and nothing else."""

    def test_bare_and_decorated_numbers(self) -> None:
        for raw_issue in ("42", " #42 ", "# 42"):
            with self.subTest(raw_issue=raw_issue):
                self.assertEqual(
                    filters.parse_issue_number(raw_issue), _ISSUE_NUMBER,
                )

    def test_blank_and_non_numeric_return_none(self) -> None:
        for raw_issue in ("", "   ", "#", "abc", "#abc"):
            with self.subTest(raw_issue=raw_issue):
                self.assertIsNone(filters.parse_issue_number(raw_issue))

    def test_non_positive_returns_none(self) -> None:
        # GitHub issue numbers start at 1, so 0 and negatives are not valid
        # drill-down targets.
        for raw_issue in ("0", "-3"):
            with self.subTest(raw_issue=raw_issue):
                self.assertIsNone(filters.parse_issue_number(raw_issue))


class ResolveStageFilterTest(unittest.TestCase):
    """The stage multiselect keeps three states apart.

    Its default ("all known non-null stages") collapses to `stages=None` so
    the read does not emit a `stage IN (...)` clause that silently excludes
    NULL-stage rows -- a legitimate case, since stage evaluation writes
    `stage=None` when the issue carries no workflow label. The cleared
    multiselect (`[]`) stays distinct so the "show nothing" path still works.
    """

    def test_all_selected_collapses_to_none(self) -> None:
        resolved = filters.resolve_stage_filter(
            selected=[*_STAGE_NAMES, _OTHER_STAGE],
            available=(*_STAGE_NAMES, _OTHER_STAGE),
        )
        self.assertIsNone(resolved)

    def test_no_available_options_returns_none(self) -> None:
        # No non-null stages recorded yet, so the read runs unconstrained on
        # the stage column.
        self.assertIsNone(
            filters.resolve_stage_filter(selected=[], available=()),
        )

    def test_cleared_multiselect_returns_empty_list(self) -> None:
        # Options exist but the operator cleared the selection. The read
        # encodes `[]` as a tautologically-false predicate; without this
        # branch the cleared state would be indistinguishable from the
        # all-selected default.
        resolved = filters.resolve_stage_filter(
            selected=[],
            available=(*_STAGE_NAMES, _OTHER_STAGE),
        )
        self.assertEqual(resolved, [])

    def test_proper_subset_passes_through(self) -> None:
        resolved = filters.resolve_stage_filter(
            selected=list(_STAGE_NAMES),
            available=(*_STAGE_NAMES, _OTHER_STAGE),
        )
        self.assertEqual(resolved, list(_STAGE_NAMES))


class CacheKeyTest(unittest.TestCase):
    """Every cached read is stored under this key.

    Streamlit hashes it, so the multiselect lists have to become tuples, and
    `None` has to survive so the tri-state filter contract (None / [] / [...])
    does not collapse at the cache layer.
    """

    def test_lists_become_tuples(self) -> None:
        window = windows.to_window(fixtures.MAY01, fixtures.MAY07)
        key = filters.cache_key(
            window,
            _CACHE_REPO,
            list(_EVENT_NAMES),
            list(_STAGE_NAMES),
            _ISSUE_NUMBER,
        )
        self.assertEqual(
            key,
            (
                window.start,
                window.end,
                _CACHE_REPO,
                _EVENT_NAMES,
                _STAGE_NAMES,
                _ISSUE_NUMBER,
            ),
        )
        hash(key)

    def test_none_is_preserved(self) -> None:
        window = windows.to_window(fixtures.MAY01, fixtures.MAY07)
        key = filters.cache_key(window, None, None, None, None)
        self.assertEqual(
            key, (window.start, window.end, None, None, None, None),
        )

    def test_empty_list_distinct_from_none(self) -> None:
        # Empty events / stages mean "cleared multiselect, show nothing"; the
        # key keeps the empty tuple distinct from None so the two SQL shapes
        # cannot collide in cache.
        window = windows.to_window(fixtures.MAY01, fixtures.MAY07)
        empty = filters.cache_key(window, _CACHE_REPO, [], [], None)
        unfiltered = filters.cache_key(window, _CACHE_REPO, None, None, None)
        self.assertNotEqual(empty, unfiltered)
        self.assertEqual(empty.events, ())
        self.assertEqual(empty.stages, ())


if __name__ == "__main__":
    unittest.main()
