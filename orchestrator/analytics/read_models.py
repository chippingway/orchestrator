# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical result-model import site, answered by the query owners.

The nineteen rows are the owners' own classes, so a result a caller unpacks
here -- or compares a read against -- is the one the read families built. This
hub publishes the union of what the five family modules beside it publish
rather than sitting on top of them, so either import site hands back the same
object.
"""

from __future__ import annotations

from orchestrator.observability.analytics.query.activity_models import (
    BackendDailyTokensRow as BackendDailyTokensRow,
    HourlyHeatmapPoint as HourlyHeatmapPoint,
    ThroughputDayRow as ThroughputDayRow,
)
from orchestrator.observability.analytics.query.cost_models import (
    BackendEfficiencyRow as BackendEfficiencyRow,
    CostCoverageRow as CostCoverageRow,
    RepoBreakdownRow as RepoBreakdownRow,
    ReviewRoundBucketRow as ReviewRoundBucketRow,
)
from orchestrator.observability.analytics.query.overview_models import (
    DataExtent as DataExtent,
    FilterOptions as FilterOptions,
    Summary as Summary,
    TimeSeriesPoint as TimeSeriesPoint,
)
from orchestrator.observability.analytics.query.run_models import (
    AgentExitRow as AgentExitRow,
    EventBreakdown as EventBreakdown,
    IssueEventRow as IssueEventRow,
    IssueSummaryRow as IssueSummaryRow,
    StageBreakdown as StageBreakdown,
)
from orchestrator.observability.analytics.query.skill_models import (
    SkillAdoptionRow as SkillAdoptionRow,
    SkillTriggerMatrixRow as SkillTriggerMatrixRow,
    SkillTriggerRateRow as SkillTriggerRateRow,
)


_COMPATIBILITY_EXPORTS = (
    BackendDailyTokensRow,
    HourlyHeatmapPoint,
    ThroughputDayRow,
    DataExtent,
    FilterOptions,
    Summary,
    TimeSeriesPoint,
    BackendEfficiencyRow,
    CostCoverageRow,
    RepoBreakdownRow,
    ReviewRoundBucketRow,
    AgentExitRow,
    EventBreakdown,
    IssueEventRow,
    IssueSummaryRow,
    StageBreakdown,
    SkillAdoptionRow,
    SkillTriggerMatrixRow,
    SkillTriggerRateRow,
)
