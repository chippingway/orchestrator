# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical run-result import site, answered by the query owner.

The five rows and the accessor beside them are the owner's own objects, so the
`result` alias installed on the trace row is the one a caller reaching this
module reads an event outcome through.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.run_models import (
    RESULT_FIELD as RESULT_FIELD,
    AgentExitRow as AgentExitRow,
    EventBreakdown as EventBreakdown,
    IssueEventRow as IssueEventRow,
    IssueSummaryRow as IssueSummaryRow,
    StageBreakdown as StageBreakdown,
    public_event_result as public_event_result,
)


_COMPATIBILITY_EXPORTS = (
    RESULT_FIELD,
    AgentExitRow,
    EventBreakdown,
    IssueEventRow,
    IssueSummaryRow,
    StageBreakdown,
    public_event_result,
)
