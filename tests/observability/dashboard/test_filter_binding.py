# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a cache key is read back as when the read it stores is issued.

The key the cases below unpack is built by the filter owner rather than
written out here, because the contract is a round trip: the positions one
module packs are the positions this one reads, and a case that hand-rolled the
tuple would keep passing after the two spellings drifted apart.
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from orchestrator.observability.dashboard import (
    filter_binding,
    filters,
    scoped_reads,
    windows,
)
from tests.observability.dashboard.dashboard_test_support import (
    MAY01,
    MAY07,
    utc_midnight,
)

_REPO = "owner/repo"

_EVENTS = ("stage_entered", "agent_exit")

_STAGES = ("implementing",)

_ISSUE = 42

_ROWS = ("row",)

_TZ_OFFSET_HOURS = 7

_SCOPED_READ_ATTRIBUTE = "scoped_read"


def _cache_key(
    events: Any = _EVENTS,
    stages: Any = _STAGES,
) -> filters.DashboardCacheKey:
    """The key a run narrowed to one repo and issue stores its reads under."""
    return filters.cache_key(
        windows.DateWindow(start=utc_midnight(MAY01), end=utc_midnight(MAY07)),
        _REPO,
        events,
        stages,
        _ISSUE,
    )


def _read(**read_filters: Any) -> tuple[str, ...]:
    return _ROWS


class FilterListTest(unittest.TestCase):
    """The three states a multiselect reaches a read in.

    A selection is hashed into the key as a tuple and read by the query owners
    as a list, and the two empty answers are not the same question: `None` is
    "no clause at all", while the cleared multiselect must match nothing.
    """

    def test_no_clause_stays_no_clause(self) -> None:
        self.assertIsNone(filter_binding.filter_list(None))

    def test_a_selection_reads_back_as_a_list(self) -> None:
        read_values = filter_binding.filter_list(_EVENTS)

        self.assertEqual(read_values, list(_EVENTS))
        self.assertIsInstance(read_values, list)

    def test_a_cleared_selection_stays_empty(self) -> None:
        self.assertEqual(filter_binding.filter_list(()), [])


class ReadFilterKwargsTest(unittest.TestCase):
    """A key the filter owner hashed reads back as the read's own vocabulary."""

    def test_the_key_reads_back_as_it_was_built(self) -> None:
        key = _cache_key()

        self.assertEqual(
            filter_binding.read_filter_kwargs(key),
            {
                "start": key.start,
                "end": key.end,
                "repo": _REPO,
                "events": list(_EVENTS),
                "stages": list(_STAGES),
                "issue": _ISSUE,
            },
        )

    def test_an_unnarrowed_key_carries_no_clause(self) -> None:
        # The page hashes "every event" and "every stage" as `None` rather than
        # as the full list, so the read is issued without the clause instead of
        # with one naming every value the filter bar happened to offer.
        read_filters = filter_binding.read_filter_kwargs(
            _cache_key(events=None, stages=None),
        )

        self.assertIsNone(read_filters["events"])
        self.assertIsNone(read_filters["stages"])


class ReadFilteredTest(unittest.TestCase):
    """A windowed read is issued through the shared scope, under that key."""

    def test_the_read_is_issued_under_that_key(self) -> None:
        key = _cache_key()

        getter, read_filters = self._issued(_read, key)

        self.assertIs(getter, _read)
        self.assertEqual(read_filters, filter_binding.read_filter_kwargs(key))

    def test_a_widget_s_own_filter_joins_them(self) -> None:
        # What a row is grouped into is not what the window holds, so the
        # display offset an activity heatmap buckets by travels beside the
        # key's filters rather than inside the key itself.
        _, read_filters = self._issued(
            _read, _cache_key(), tz_offset_hours=_TZ_OFFSET_HOURS,
        )

        self.assertEqual(read_filters["tz_offset_hours"], _TZ_OFFSET_HOURS)

    def _issued(self, getter: Any, key: Any, **extra: Any) -> tuple[Any, dict]:
        """The getter and filters `read_filtered` handed the scope owner."""
        with patch.object(
            scoped_reads, _SCOPED_READ_ATTRIBUTE,
        ) as scoped_read:
            read_rows = filter_binding.read_filtered(getter, key, **extra)
            self.assertIs(read_rows, scoped_read.return_value)
            issued = scoped_read.call_args
        return issued.args[0], issued.kwargs


if __name__ == "__main__":
    unittest.main()
