# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Immutable lazy-export inventory for analytics reads."""

from __future__ import annotations

from orchestrator._compat_exports import export_group

EXPORTS = (
    # The result models answer off the canonical owners too, so a row a caller
    # unpacks off this facade is the class the read families constructed --
    # `isinstance` against either import site holds.
    *export_group(
        "orchestrator.observability.analytics.query.activity_models",
        (
            ("BackendDailyTokensRow", "BackendDailyTokensRow"),
            ("HourlyHeatmapPoint", "HourlyHeatmapPoint"),
            ("ThroughputDayRow", "ThroughputDayRow"),
        ),
    ),
    *export_group(
        "orchestrator.observability.analytics.query.overview_models",
        (
            ("DataExtent", "DataExtent"),
            ("FilterOptions", "FilterOptions"),
            ("Summary", "Summary"),
            ("TimeSeriesPoint", "TimeSeriesPoint"),
        ),
    ),
    *export_group(
        "orchestrator.observability.analytics.query.cost_models",
        (
            ("BackendEfficiencyRow", "BackendEfficiencyRow"),
            ("CostCoverageRow", "CostCoverageRow"),
            ("RepoBreakdownRow", "RepoBreakdownRow"),
            ("ReviewRoundBucketRow", "ReviewRoundBucketRow"),
        ),
    ),
    *export_group(
        "orchestrator.observability.analytics.query.run_models",
        (
            ("AgentExitRow", "AgentExitRow"),
            ("EventBreakdown", "EventBreakdown"),
            ("IssueEventRow", "IssueEventRow"),
            ("IssueSummaryRow", "IssueSummaryRow"),
            ("StageBreakdown", "StageBreakdown"),
        ),
    ),
    *export_group(
        "orchestrator.observability.analytics.query.skill_models",
        (
            ("SkillAdoptionRow", "SkillAdoptionRow"),
            ("SkillTriggerMatrixRow", "SkillTriggerMatrixRow"),
            ("SkillTriggerRateRow", "SkillTriggerRateRow"),
        ),
    ),
    # Every read answers off its canonical owner, so a call made through this
    # facade runs the same SQL and short circuits as one made through the query
    # package directly.
    *export_group(
        "orchestrator.observability.analytics.query.issue_summaries",
        (
            ("SORT_BY_COST", "SORT_BY_COST"),
            ("SORT_BY_LAST_SEEN", "SORT_BY_LAST_SEEN"),
        ),
    ),
    *export_group(
        "orchestrator.observability.analytics.query.raw_reads",
        (
            ("get_data_extent", "get_data_extent"),
            ("get_event_breakdown", "get_event_breakdown"),
            ("get_filter_options", "get_filter_options"),
            ("get_issue_events", "get_issue_events"),
            ("get_issues", "get_issues"),
            ("get_recent_agent_exits", "get_recent_agent_exits"),
        ),
    ),
    *export_group(
        "orchestrator.observability.analytics.query.breakdown_reads",
        (
            ("get_backend_daily_tokens", "get_backend_daily_tokens"),
            ("get_cost_coverage", "get_cost_coverage"),
            ("get_hourly_heatmap", "get_hourly_heatmap"),
            ("get_review_round_breakdown", "get_review_round_breakdown"),
        ),
    ),
    *export_group(
        "orchestrator.observability.analytics.query.skill_reads",
        (
            ("get_skill_adoption", "get_skill_adoption"),
            ("get_skill_trigger_matrix", "get_skill_trigger_matrix"),
            ("get_skill_trigger_rates", "get_skill_trigger_rates"),
        ),
    ),
    *export_group(
        "orchestrator.observability.analytics.query.rollup_reads",
        (
            ("get_backend_efficiency", "get_backend_efficiency"),
            ("get_kpi_prev", "get_kpi_prev"),
            ("get_repo_breakdown", "get_repo_breakdown"),
            ("get_stage_breakdown", "get_stage_breakdown"),
            ("get_summary", "get_summary"),
            ("get_throughput_breakdown", "get_throughput_breakdown"),
            ("get_time_series", "get_time_series"),
        ),
    ),
    # The connection half of this surface answers off the canonical owners,
    # under the underscore-prefixed names the facade published them as: a
    # historical private name is what a caller already imported, and the owner
    # it resolves to is where the behavior is now maintained.
    *export_group(
        "orchestrator.observability.analytics.query.connections",
        (
            ("AnalyticsReadError", "AnalyticsReadError"),
            ("_close_quietly", "close_quietly"),
            ("_default_connect", "default_connect"),
            ("_default_persistent_connect", "default_persistent_connect"),
            ("_is_broken_connection_exc", "is_broken_connection_exc"),
        ),
    ),
    *export_group(
        "orchestrator.observability.analytics.query.connection_cache",
        (
            ("analytics_connection", "analytics_connection"),
            ("close_thread_local_connection", "close_thread_local_connection"),
            ("_thread_local", "thread_local"),
        ),
    ),
)

EXPORTED_NAMES = tuple(sorted(target.export_name for target in EXPORTS))
