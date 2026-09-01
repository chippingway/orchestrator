# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which window is worth interrupting, and with which banner.

A threshold is what an opening line is decided by, so each is read from both
sides here: a window that crosses it, a window under it, and a window with
nothing to divide by at all. What the banner then says is pinned beside the
severity it carries, because the counts an operator acts on live in the message
text rather than in a field next to it -- a message that stopped naming them
would still be a banner of the right colour.

The two bands are also read together, since one window can cross both and the
order the banners arrive in is the order the page stacks them: the runs that
failed first, then the spend that could not be priced.
"""

from __future__ import annotations

import unittest

from orchestrator.observability.analytics.query.cost_models import CostCoverageRow
from orchestrator.observability.analytics.query.overview_models import Summary
from orchestrator.observability.dashboard import insights

_ERROR = "error"

_WARNING = "warning"

# What the parser writes when no rate table covered the SKU, and what a NULL
# column is bucketed under. The coverage ratio counts the two together.
_UNKNOWN_PRICE = "unknown-price"

_NULL_SOURCE = "unknown"

_PRICED_SOURCE = "reported"

# Three failures in ten runs -- three times the tenth the error band sits at.
_FAILING_RUNS = 10

_FAILURES = 3

# One failure in ten: the band itself, which is raised rather than skipped.
_BAND_FAILURES = 1

# Five in a hundred, half the band, and fifty clean runs beside it.
_QUIET_RUNS = 100

_QUIET_FAILURES = 5

_CLEAN_RUNS = 50

# Thirty unpriced runs in a hundred, split across both unpriced spellings.
_PRICED_RUNS = 70

_UNKNOWN_PRICE_RUNS = 20

_NULL_SOURCE_RUNS = 10

# One unpriced run in a hundred, a tenth of the band.
_MOSTLY_PRICED_RUNS = 99

_SINGLE_RUN = 1


def _summary(*, agent_runs: int = 0, failed: int = 0) -> Summary:
    """A window whose agent-run totals are all the failure band reads."""
    return Summary(total_agent_runs=agent_runs, failed_agent_runs=failed)


def _coverage(*pairs: tuple[str, int]) -> tuple[CostCoverageRow, ...]:
    """The cost-source split the unpriced share is measured over."""
    return tuple(
        CostCoverageRow(cost_source=source, runs=runs)
        for source, runs in pairs
    )


class FailureBannerTest(unittest.TestCase):
    """The band a window's non-zero exits are raised as an error at."""

    def test_a_crossed_band_names_the_counts(self) -> None:
        banners = insights.compute_insights(
            _summary(agent_runs=_FAILING_RUNS, failed=_FAILURES),
        )
        self.assertEqual([banner.severity for banner in banners], [_ERROR])
        self.assertIn("3 of 10", banners[0].message)

    def test_the_band_itself_is_crossed(self) -> None:
        banners = insights.compute_insights(
            _summary(agent_runs=_FAILING_RUNS, failed=_BAND_FAILURES),
        )
        self.assertEqual([banner.severity for banner in banners], [_ERROR])

    def test_a_window_under_it_is_quiet(self) -> None:
        # The empty window is listed beside the healthy ones because it is the
        # only one the ratio cannot be taken over at all.
        windows = (
            _summary(agent_runs=_QUIET_RUNS, failed=_QUIET_FAILURES),
            _summary(agent_runs=_CLEAN_RUNS),
            _summary(),
        )
        for summary in windows:
            with self.subTest(agent_runs=summary.total_agent_runs):
                self.assertEqual(insights.compute_insights(summary), [])


class UnpricedCoverageBannerTest(unittest.TestCase):
    """The band an unpriced share of a window is warned about at."""

    def test_both_unpriced_spellings_count(self) -> None:
        banners = insights.compute_insights(
            _summary(),
            cost_coverage_rows=_coverage(
                (_PRICED_SOURCE, _PRICED_RUNS),
                (_UNKNOWN_PRICE, _UNKNOWN_PRICE_RUNS),
                (_NULL_SOURCE, _NULL_SOURCE_RUNS),
            ),
        )
        self.assertEqual([banner.severity for banner in banners], [_WARNING])
        self.assertIn("30 of 100", banners[0].message)

    def test_a_share_under_it_is_quiet(self) -> None:
        # A window with no coverage rows at all shares the answer: a page that
        # read no split is not a page whose runs went unpriced.
        splits = (
            _coverage(
                (_PRICED_SOURCE, _MOSTLY_PRICED_RUNS),
                (_UNKNOWN_PRICE, _SINGLE_RUN),
            ),
            _coverage((_UNKNOWN_PRICE, 0)),
            (),
        )
        for rows in splits:
            with self.subTest(rows=rows):
                self.assertEqual(
                    insights.compute_insights(
                        _summary(), cost_coverage_rows=rows,
                    ),
                    [],
                )


class BannerOrderTest(unittest.TestCase):
    """A window crossing both bands is stacked in the page's order."""

    def test_failures_are_named_before_pricing(self) -> None:
        banners = insights.compute_insights(
            _summary(agent_runs=_FAILING_RUNS, failed=_FAILURES),
            cost_coverage_rows=_coverage(
                (_PRICED_SOURCE, _PRICED_RUNS),
                (_UNKNOWN_PRICE, _UNKNOWN_PRICE_RUNS + _NULL_SOURCE_RUNS),
            ),
        )
        self.assertEqual(
            [banner.severity for banner in banners], [_ERROR, _WARNING],
        )


if __name__ == "__main__":
    unittest.main()
