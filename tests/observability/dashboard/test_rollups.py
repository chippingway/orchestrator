# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which read a headline or lifecycle section is drawn from, and under what.

An adapter here settles three things and nothing else: the query owner's read
a section is answered by, the key that read is issued under, and the cap the
two capped reads carry beside it. So the cases below patch the binding all
seven travel through and read back what was handed to it, rather than standing
a database up to observe the same facts through rows.

The key is built by the filter owner rather than written out here, because what
an adapter owes a page is its own key passed through untouched -- a hand-rolled
tuple would keep passing after the two spellings drifted apart. The ranking
depth is read off the KPI owner for the same reason: a literal repeated here
would keep passing after the rows fetched and the rows drawn stopped agreeing.
"""

from __future__ import annotations

import inspect
import unittest
from typing import Any
from unittest.mock import patch

from orchestrator.observability.analytics.query import (
    breakdown_reads,
    issue_summaries,
    raw_reads,
    rollup_reads,
)
from orchestrator.observability.dashboard import (
    filter_binding,
    filters,
    kpis,
    rollups,
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

_READ_FILTERED_ATTRIBUTE = "read_filtered"

_LIMIT_PARAMETER = "limit"

_SORT_PARAMETER = "sort_by"

# How many of the newest agent runs a page can show at once.
_RECENT_EXIT_CAP = 100

# The key a run narrowed to one repo and issue stores its reads under.
_KEY = filters.cache_key(
    windows.DateWindow(start=utc_midnight(MAY01), end=utc_midnight(MAY07)),
    _REPO,
    _EVENTS,
    _STAGES,
    _ISSUE,
)

# What a page hands an adapter, which is what its cached key is built out of.
# A connection may never appear here: `st.cache_data` would have to hash a
# psycopg connection, which is unhashable, and a stringified one would make
# every refreshed socket look like a cache miss.
_KEY_ONLY = ("key",)

# Each read and the query owner's read it names. Four are the day-bucketed
# rollups a window is summarized and plotted from, the review-round split is
# what that bucket threw a column away for, and the newest runs and the
# per-issue spend rows are scanned off the raw events table under no bucket.
_SECTION_READS = (
    (rollups.read_summary, rollup_reads.get_summary),
    (rollups.read_prev_kpi, rollup_reads.get_kpi_prev),
    (rollups.read_time_series, rollup_reads.get_time_series),
    (rollups.read_stage_breakdown, rollup_reads.get_stage_breakdown),
    (rollups.read_recent_agent_exits, raw_reads.get_recent_agent_exits),
    (rollups.read_top_cost_issues, raw_reads.get_issues),
    (rollups.read_review_round, breakdown_reads.get_review_round_breakdown),
)

# The five answering a whole window, which is the whole of what their key says.
_UNCAPPED_READS = (
    rollups.read_summary,
    rollups.read_prev_kpi,
    rollups.read_time_series,
    rollups.read_stage_breakdown,
    rollups.read_review_round,
)


class _SectionReadSupport(unittest.TestCase):
    """Reads back what one adapter handed the binding it issues through."""

    def _issued(self, read: Any) -> Any:
        """What one adapter handed the binding, having handed its rows back."""
        with patch.object(
            filter_binding, _READ_FILTERED_ATTRIBUTE,
        ) as read_filtered:
            read_rows = read(_KEY)
            self.assertIs(read_rows, read_filtered.return_value)
            return read_filtered.call_args


class SectionReadOwnerTest(_SectionReadSupport):
    """Each read issues its own query owner's read under the page's key."""

    def test_each_read_names_its_query_owner(self) -> None:
        # Identity, not behavior: a read bound to a copy of the owner's
        # function would answer every section correctly and still leave a patch
        # aimed at that owner intercepting nothing.
        for read, getter in _SECTION_READS:
            with self.subTest(read=read.__name__):
                issued = self._issued(read)

                self.assertIs(issued.args[0], getter)
                self.assertIs(issued.args[1], _KEY)

    def test_the_previous_window_skips_the_summary(self) -> None:
        # The delta pills and the cost-trend banner read a handful of scalars
        # off the window before this one, so the previous read is answered by
        # the KPI-only rollup. Falling back to the full summary shape would put
        # a second whole-window scan on every cold load.
        issued = self._issued(rollups.read_prev_kpi)

        self.assertIsNot(issued.args[0], rollup_reads.get_summary)

    def test_uncapped_reads_narrow_by_nothing_else(self) -> None:
        # A section answering a whole window is narrowed by that window and the
        # selections every other read shares, so a filter passed beside the key
        # here would be one the page never asked for.
        for read in _UNCAPPED_READS:
            with self.subTest(read=read.__name__):
                self.assertEqual(self._issued(read).kwargs, {})


class CappedReadTest(_SectionReadSupport):
    """The two reads a page cannot show the whole answer of carry their cap."""

    def test_the_run_list_stops_at_the_newest_hundred(self) -> None:
        # What keeps the run list readable on a long window -- and why the
        # reliability tiles above it are reduced from the window's own totals
        # rather than from these rows.
        issued = self._issued(rollups.read_recent_agent_exits)

        self.assertEqual(rollups.DEFAULT_RECENT_AGENT_EXITS, _RECENT_EXIT_CAP)
        self.assertEqual(
            issued.kwargs, {_LIMIT_PARAMETER: _RECENT_EXIT_CAP},
        )

    def test_the_spend_table_reads_the_rows_it_ranks(self) -> None:
        # Cost-first is what makes the cut meaningful, and the depth is the KPI
        # owner's so the rows fetched and the rows drawn stay one number.
        issued = self._issued(rollups.read_top_cost_issues)

        self.assertEqual(
            issued.kwargs,
            {
                _LIMIT_PARAMETER: kpis.DEFAULT_EXPENSIVE_LIMIT,
                _SORT_PARAMETER: issue_summaries.SORT_BY_COST,
            },
        )

    def test_the_ranking_depth_is_read_at_call_time(self) -> None:
        # A page that re-cut the table would otherwise fetch the depth this
        # module was imported with rather than the one the KPI owner holds.
        deeper = kpis.DEFAULT_EXPENSIVE_LIMIT + 1
        with patch.object(kpis, "DEFAULT_EXPENSIVE_LIMIT", deeper):
            issued = self._issued(rollups.read_top_cost_issues)

        self.assertEqual(issued.kwargs[_LIMIT_PARAMETER], deeper)


class CacheKeySignatureTest(unittest.TestCase):
    """A page's call is the whole of what a cached read is stored under."""

    def test_each_read_takes_the_key_alone(self) -> None:
        for read, _ in _SECTION_READS:
            with self.subTest(read=read.__name__):
                self.assertEqual(
                    tuple(inspect.signature(read).parameters),
                    _KEY_ONLY,
                )


if __name__ == "__main__":
    unittest.main()
