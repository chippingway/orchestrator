# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical query-row import site, answered by the query owner.

The three row types are the owner's own classes and the constructors beside
them its own functions, so a row named here is the row the projections unpack,
padding included.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.query_rows import (
    AgentExitQueryRow as AgentExitQueryRow,
    IssueSummaryQueryRow as IssueSummaryQueryRow,
    ReviewRoundQueryRow as ReviewRoundQueryRow,
    agent_exit_row as agent_exit_row,
    issue_summary_row as issue_summary_row,
    review_round_row as review_round_row,
)


_COMPATIBILITY_EXPORTS = (
    AgentExitQueryRow,
    IssueSummaryQueryRow,
    ReviewRoundQueryRow,
    agent_exit_row,
    issue_summary_row,
    review_round_row,
)
