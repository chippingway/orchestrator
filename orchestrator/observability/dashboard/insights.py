# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The observations a page is interrupted with, above every panel it draws.

A banner here is something an operator should act on rather than a number to
read off a chart, so the whole owner is the two questions worth stopping a page
for and the ratio each is raised at. A window whose agent runs exit non-zero
more than a tenth of the time is describing a broken workload rather than the
one the panels below it plot; a window whose runs arrive unpriced that often is
one whose spend is an undercount, because the rate tables in
`observability/usage/prices.py` are missing SKUs the parser is seeing in the
wild.

Each threshold sits beside the arithmetic that crosses it: what is worth
interrupting for is one decision, and a page carrying its own copy of either
number is where the banner raised and the banner documented would drift apart.
Which rows answer them follows the same rule -- the failure ratio is read off
the window's own totals, and the coverage ratio off the cost-source split a
comparison panel is drawn from, so neither is re-derived per page.

Crossing nothing is the ordinary answer, and it is an empty list rather than a
banner saying so, because the caller branches on it for a section header that
would otherwise sit above nothing.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from orchestrator.observability.analytics.query.cost_models import CostCoverageRow
from orchestrator.observability.analytics.query.overview_models import Summary

FAILURE_RATE_BANNER_THRESHOLD = 0.1
UNPRICED_COVERAGE_THRESHOLD = 0.1
# The two spellings a run the parser could not price arrives under: what it
# writes when no rate table covered the SKU, and what a NULL column is bucketed
# as. Both are the same gap from the operator's side, so the ratio counts them
# together even though the coverage bar keeps them apart.
UNPRICED_COST_SOURCES: frozenset[str] = frozenset(("unknown-price", "unknown"))


@dataclass(frozen=True)
class InsightBanner:
    """A single banner line displayed at the top of the page.

    `severity` is one of `success` / `info` / `warning` / `error`;
    the dashboard renders each through the matching coloured insight
    block. Keeping severity a plain string (rather than an Enum)
    means the helpers stay importable without Streamlit and the
    tests can compare against string literals.
    """

    severity: str
    message: str


def compute_insights(
    summary: Summary,
    *,
    cost_coverage_rows: Sequence[CostCoverageRow] = (),
) -> list[InsightBanner]:
    """Banner lines surfaced at the top of the redesigned page.

    Each banner is a single observation the operator should act on:

    - Failure rate exceeds `FAILURE_RATE_BANNER_THRESHOLD`: agent
      runs are exiting non-zero more than 10 % of the time.
    - Unpriced cost coverage exceeds `UNPRICED_COVERAGE_THRESHOLD`:
      the price tables in `observability/usage/prices.py` are
      missing SKUs the parser is seeing in the wild.

    The helper returns an empty list when nothing crosses a
    threshold, so the caller can branch on `if banners:` for the
    section header.
    """
    banners: list[InsightBanner] = []
    if summary.total_agent_runs > 0:
        rate = summary.failed_agent_runs / summary.total_agent_runs
        if rate >= FAILURE_RATE_BANNER_THRESHOLD:
            rate *= 100
            banners.append(
                InsightBanner(
                    severity="error",
                    message=(
                        f"{summary.failed_agent_runs} of "
                        f"{summary.total_agent_runs} agent runs failed "
                        f"({rate:.0f}%)."
                    ),
                )
            )
    if cost_coverage_rows:
        total_runs = sum(row.runs for row in cost_coverage_rows)
        unpriced = sum(
            row.runs
            for row in cost_coverage_rows
            if row.cost_source in UNPRICED_COST_SOURCES
        )
        if total_runs > 0:
            ratio = unpriced / total_runs
            if ratio >= UNPRICED_COVERAGE_THRESHOLD:
                ratio *= 100
                banners.append(
                    InsightBanner(
                        severity="warning",
                        message=(
                            f"{unpriced} of {total_runs} agent runs lack "
                            f"a priced cost ({ratio:.0f}%) -- check "
                            "the price tables in "
                            "`observability/usage/prices.py` "
                            "for missing SKUs."
                        ),
                    )
                )
    return banners
