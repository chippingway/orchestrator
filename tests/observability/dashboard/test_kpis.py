# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a window's headline numbers say at the edges the arithmetic has.

Each of the four reductions is read where it can go wrong rather than on a
typical window: a delta with nothing to divide by, a window with no runs to
take a success rate over, a table of issues that tie on cost or carry none at
all, and a breakdown whose buckets sit on both sides of the initial pass. The
plain window is pinned beside each, because an edge answer only means something
while the ordinary one is still right.

The tile cases read the tones as well as the counts, since the tone is what
paints the tile: a failure count that arrived correct under a neutral tone is a
panel reading as healthy while reporting failures. The ranking cases read whole
`(repo, issue)` pairs rather than a first row, because the order is a total one
-- ties fall back to run count and then to the pair that names the issue -- and
a check on the head alone would pass while the tail reshuffled between reruns.
"""

from __future__ import annotations

import unittest
from typing import Optional

from orchestrator.observability.analytics.query.cost_models import (
    ReviewRoundBucketRow,
)
from orchestrator.observability.analytics.query.overview_models import Summary
from orchestrator.observability.analytics.query.run_models import IssueSummaryRow
from orchestrator.observability.dashboard import kpis
from tests.observability.dashboard.dashboard_test_support import (
    MAY01,
    MAY02,
    utc_midnight,
)


# The labels the six tiles are keyed by, which is also the order the panel
# renders them in.
_AGENT_RUNS = "Agent runs"

_SUCCESS_RATE = "Success rate"

_RESOLVED = "Resolved"

_REJECTED = "Rejected"

_FAILURES = "Failures"

_TIMEOUTS = "Timeouts"

# The CSS class each count is painted through once it crosses zero.
_WARN = "warn"

_BAD = "bad"

_NEUTRAL = ""

# A window holding far more agent runs than the recent-runs read is capped at,
# so a tile summing that read would miss most of both counts.
_WINDOW_RUNS = 250

_WINDOW_FAILURES = 4

_WINDOW_TIMEOUTS = 17

_WINDOW_RESOLVED = 12

_WINDOW_REJECTED = 2

# A quarter more and a quarter less than the window before it.
_GROWN = 125.0

_SHRUNK = 75.0

_BASELINE = 100.0

_QUARTER = 0.25

# A window with runs but nothing wrong with them.
_HEALTHY_RUNS = 20

_REPO_A = "acme/a"

_REPO_B = "acme/b"

_REPO_C = "acme/c"

_STAGE = "implementing"

# Three issues whose spend orders them C, B, A -- read back through the two
# ranked above the cheapest.
_HIGH_COST = 1.0

_MID_COST = 0.5

_LOW_COST = 0.1

# The runs one issue is credited with against the two its ties are broken over.
_BUSY_RUNS = 10

_QUIET_RUNS = 2

# One initial-pass round and one review round beside it.
_INITIAL_COST = 50.0

_REWORK_COST = 20.0

_ROUND_ONE = "1"

# The two buckets whose runs are not a second pass: the initial development
# round, and the runs whose review round was never recorded.
_NOT_REWORK_BUCKETS = ("0", "unknown")


def _summary(**counts: int) -> Summary:
    """A window whose agent-run totals are all the tiles read."""
    return Summary(**counts)


def _tiles(summary: Summary, **throughput: int) -> dict:
    """`reliability_tile_data` triples projected to `{label: (value, tone)}`."""
    return {
        label: (tile_value, tone)
        for tile_value, label, tone in kpis.reliability_tile_data(
            summary, **throughput,
        )
    }


def _issue(
    repo: str, number: int, cost: Optional[float], runs: int = 1,
) -> IssueSummaryRow:
    """An issue row carrying only the columns the ranking orders on."""
    return IssueSummaryRow(
        repo=repo,
        issue=number,
        event_count=runs,
        first_seen=utc_midnight(MAY01),
        last_seen=utc_midnight(MAY02),
        latest_stage=_STAGE,
        agent_exits=1,
        total_cost_usd=cost,
        total_input_tokens=0,
        total_output_tokens=0,
    )


class KpiDeltaTest(unittest.TestCase):
    """The relative move a tile is annotated with, against the window before."""

    def test_a_move_is_read_in_both_directions(self) -> None:
        moves = ((_GROWN, _QUARTER), (_SHRUNK, -_QUARTER))
        for current, expected in moves:
            with self.subTest(current=current):
                self.assertAlmostEqual(
                    kpis.kpi_delta(current, _BASELINE), expected,
                )

    def test_an_unusable_baseline_has_no_delta(self) -> None:
        # Nothing to divide by, so the page hides the indicator rather than
        # rendering an infinity. The negative baseline is listed beside zero
        # because these columns are counts and spend: one arriving below zero
        # is a broken read, not a window that shrank.
        for previous in (0, -_BASELINE):
            with self.subTest(previous=previous):
                self.assertIsNone(kpis.kpi_delta(_HEALTHY_RUNS, previous))


class ReliabilityTileTest(unittest.TestCase):
    """The six tiles a window's run health is read off."""

    def test_every_count_comes_off_the_window(self) -> None:
        tiles = _tiles(
            _summary(
                total_agent_runs=_WINDOW_RUNS,
                failed_agent_runs=_WINDOW_FAILURES,
                timed_out_agent_runs=_WINDOW_TIMEOUTS,
            ),
            resolved=_WINDOW_RESOLVED,
            rejected=_WINDOW_REJECTED,
        )
        self.assertEqual(tiles[_AGENT_RUNS][0], _WINDOW_RUNS)
        self.assertEqual(tiles[_FAILURES], (_WINDOW_FAILURES, _WARN))
        self.assertEqual(tiles[_TIMEOUTS], (_WINDOW_TIMEOUTS, _BAD))
        self.assertEqual(tiles[_RESOLVED][0], _WINDOW_RESOLVED)
        self.assertEqual(tiles[_REJECTED], (_WINDOW_REJECTED, _WARN))

    def test_an_empty_window_still_renders(self) -> None:
        # No runs to take a rate over: the panel reports 0% so an operator can
        # confirm the window really is empty, rather than failing to draw.
        tiles = _tiles(_summary())
        self.assertEqual(tiles[_AGENT_RUNS][0], 0)
        self.assertEqual(tiles[_SUCCESS_RATE][0], "0%")
        self.assertEqual(tiles[_TIMEOUTS][0], 0)

    def test_a_clean_window_reads_neutral(self) -> None:
        tiles = _tiles(_summary(total_agent_runs=_HEALTHY_RUNS))
        self.assertEqual(tiles[_SUCCESS_RATE][0], "100%")
        self.assertEqual(tiles[_FAILURES][1], _NEUTRAL)
        self.assertEqual(tiles[_TIMEOUTS][1], _NEUTRAL)
        self.assertEqual(tiles[_REJECTED][1], _NEUTRAL)


class TopExpensiveIssuesTest(unittest.TestCase):
    """The order the "where did spend go" table is drawn in."""

    def test_the_costliest_issues_come_first(self) -> None:
        rows = (
            _issue(_REPO_A, 1, _LOW_COST),
            _issue(_REPO_B, 2, _HIGH_COST),
            _issue(_REPO_C, 3, _MID_COST),
        )
        top = kpis.top_expensive_issues(rows, limit=2)
        self.assertEqual(
            [(row.repo, row.issue) for row in top],
            [(_REPO_B, 2), (_REPO_C, 3)],
        )

    def test_an_unpriced_issue_sorts_last(self) -> None:
        # A missing cost is not a cheap one: the issue still belongs in the
        # table, below every issue whose spend was recorded.
        rows = (_issue(_REPO_A, 1, None), _issue(_REPO_B, 2, _LOW_COST))
        top = kpis.top_expensive_issues(rows)
        self.assertEqual([row.issue for row in top], [2, 1])

    def test_asking_for_no_rows_returns_none(self) -> None:
        rows = (_issue(_REPO_A, 1, _LOW_COST),)
        self.assertEqual(kpis.top_expensive_issues(rows, limit=0), [])

    def test_ties_fall_back_to_runs_then_name(self) -> None:
        rows = (
            _issue(_REPO_A, 1, _HIGH_COST, runs=_QUIET_RUNS),
            _issue(_REPO_A, 2, _HIGH_COST, runs=_BUSY_RUNS),
            _issue(_REPO_B, 1, _HIGH_COST, runs=_QUIET_RUNS),
        )
        top = kpis.top_expensive_issues(rows)
        self.assertEqual(
            [(row.repo, row.issue) for row in top],
            [(_REPO_A, 2), (_REPO_A, 1), (_REPO_B, 1)],
        )


class ReworkTotalsTest(unittest.TestCase):
    """Which review-round buckets the rework share is measured over."""

    def test_only_a_later_round_counts_as_rework(self) -> None:
        # The initial round and the unrecorded one are both spend the window
        # holds and neither is a second pass, so each lands in the total alone.
        for bucket in _NOT_REWORK_BUCKETS:
            with self.subTest(bucket=bucket):
                total, rework = kpis.rework_totals((
                    ReviewRoundBucketRow(
                        bucket=bucket, runs=3, total_cost_usd=_INITIAL_COST,
                    ),
                    ReviewRoundBucketRow(
                        bucket=_ROUND_ONE, runs=2, total_cost_usd=_REWORK_COST,
                    ),
                ))
                self.assertAlmostEqual(total, _INITIAL_COST + _REWORK_COST)
                self.assertAlmostEqual(rework, _REWORK_COST)

    def test_an_empty_breakdown_is_zero(self) -> None:
        self.assertEqual(kpis.rework_totals(()), (float(), float()))


if __name__ == "__main__":
    unittest.main()
