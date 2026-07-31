# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the temporary flat read modules still answer for on the query side."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType

_READ_FACADE = "orchestrator.analytics.read"

_CONNECTIONS = "orchestrator.observability.analytics.query.connections"

_CONNECTION_CACHE = "orchestrator.observability.analytics.query.connection_cache"

_CONDITIONS = "orchestrator.observability.analytics.query.conditions"

_FILTERS = "orchestrator.observability.analytics.query.filters"

_PREDICATES = "orchestrator.observability.analytics.query.predicates"

_REQUEST_MODELS = "orchestrator.observability.analytics.query.request_models"

_REQUESTS = "orchestrator.observability.analytics.query.requests"

_ACTIVITY_MODELS = "orchestrator.observability.analytics.query.activity_models"

_COST_MODELS = "orchestrator.observability.analytics.query.cost_models"

_OVERVIEW_MODELS = "orchestrator.observability.analytics.query.overview_models"

_RUN_MODELS = "orchestrator.observability.analytics.query.run_models"

_SKILL_MODELS = "orchestrator.observability.analytics.query.skill_models"

_AGENT_EXITS = "orchestrator.observability.analytics.query.agent_exits"

_EVENT_BREAKDOWNS = "orchestrator.observability.analytics.query.event_breakdowns"

_FILTER_OPTIONS = "orchestrator.observability.analytics.query.filter_options"

_ISSUE_EVENTS = "orchestrator.observability.analytics.query.issue_events"

_ISSUE_SUMMARIES = "orchestrator.observability.analytics.query.issue_summaries"

_QUERY_ROWS = "orchestrator.observability.analytics.query.query_rows"

_RAW_READS = "orchestrator.observability.analytics.query.raw_reads"

_RAW_VALUES = "orchestrator.observability.analytics.query.raw_values"

_BACKEND_EFFICIENCY = "orchestrator.observability.analytics.query.backend_efficiency"

_BACKEND_TOKENS = "orchestrator.observability.analytics.query.backend_tokens"

_BREAKDOWN_READS = "orchestrator.observability.analytics.query.breakdown_reads"

_CACHE_SHARES = "orchestrator.observability.analytics.query.cache_shares"

_COST_COVERAGE = "orchestrator.observability.analytics.query.cost_coverage"

_HOURLY_HEATMAPS = "orchestrator.observability.analytics.query.hourly_heatmaps"

_REVIEW_ROUNDS = "orchestrator.observability.analytics.query.review_rounds"

_SKILL_ADOPTION = "orchestrator.observability.analytics.query.skill_adoption"

_SKILL_MATRICES = "orchestrator.observability.analytics.query.skill_matrices"

_SKILL_READS = "orchestrator.observability.analytics.query.skill_reads"

_SKILL_SESSIONS = "orchestrator.observability.analytics.query.skill_sessions"

_SKILL_TRIGGER_RATES = (
    "orchestrator.observability.analytics.query.skill_trigger_rates"
)

_SKILL_VALUES = "orchestrator.observability.analytics.query.skill_values"

_KPI_TOTALS = "orchestrator.observability.analytics.query.kpi_totals"

_REPO_BREAKDOWNS = "orchestrator.observability.analytics.query.repo_breakdowns"

_ROLLUP_READS = "orchestrator.observability.analytics.query.rollup_reads"

_ROW_CELLS = "orchestrator.observability.analytics.query.row_cells"

_STAGE_BREAKDOWNS = "orchestrator.observability.analytics.query.stage_breakdowns"

_SUMMARY_QUERIES = "orchestrator.observability.analytics.query.summary_queries"

_SUMMARY_RESULTS = "orchestrator.observability.analytics.query.summary_results"

_THROUGHPUT_DAYS = "orchestrator.observability.analytics.query.throughput_days"

_TIME_SERIES = "orchestrator.observability.analytics.query.time_series"

# The result classes each family owner defines, named once and read by both
# checks below: a page unpacks a row off the facade and constructs the empty
# shape off a flat module, and an `isinstance` between the two has to hold.
_ACTIVITY_MODEL_NAMES = (
    ("BackendDailyTokensRow", _ACTIVITY_MODELS, "BackendDailyTokensRow"),
    ("HourlyHeatmapPoint", _ACTIVITY_MODELS, "HourlyHeatmapPoint"),
    ("ThroughputDayRow", _ACTIVITY_MODELS, "ThroughputDayRow"),
)

_COST_MODEL_NAMES = (
    ("BackendEfficiencyRow", _COST_MODELS, "BackendEfficiencyRow"),
    ("CostCoverageRow", _COST_MODELS, "CostCoverageRow"),
    ("RepoBreakdownRow", _COST_MODELS, "RepoBreakdownRow"),
    ("ReviewRoundBucketRow", _COST_MODELS, "ReviewRoundBucketRow"),
)

_OVERVIEW_MODEL_NAMES = (
    ("DataExtent", _OVERVIEW_MODELS, "DataExtent"),
    ("FilterOptions", _OVERVIEW_MODELS, "FilterOptions"),
    ("Summary", _OVERVIEW_MODELS, "Summary"),
    ("TimeSeriesPoint", _OVERVIEW_MODELS, "TimeSeriesPoint"),
)

_RUN_MODEL_NAMES = (
    ("AgentExitRow", _RUN_MODELS, "AgentExitRow"),
    ("EventBreakdown", _RUN_MODELS, "EventBreakdown"),
    ("IssueEventRow", _RUN_MODELS, "IssueEventRow"),
    ("IssueSummaryRow", _RUN_MODELS, "IssueSummaryRow"),
    ("StageBreakdown", _RUN_MODELS, "StageBreakdown"),
)

_SKILL_MODEL_NAMES = (
    ("SkillAdoptionRow", _SKILL_MODELS, "SkillAdoptionRow"),
    ("SkillTriggerMatrixRow", _SKILL_MODELS, "SkillTriggerMatrixRow"),
    ("SkillTriggerRateRow", _SKILL_MODELS, "SkillTriggerRateRow"),
)

_MODEL_NAMES = (
    *_ACTIVITY_MODEL_NAMES,
    *_COST_MODEL_NAMES,
    *_OVERVIEW_MODEL_NAMES,
    *_RUN_MODEL_NAMES,
    *_SKILL_MODEL_NAMES,
)

# The two orderings the issues table is read in, published under the same name
# by the facade, the raw hub, and the leaf beneath it.
_SORT_MODE_NAMES = (
    ("SORT_BY_COST", _ISSUE_SUMMARIES, "SORT_BY_COST"),
    ("SORT_BY_LAST_SEEN", _ISSUE_SUMMARIES, "SORT_BY_LAST_SEEN"),
)

# The six public raw reads and the sort modes beside them, named once and read
# by both checks below: a page calls one off the facade, and the call has to
# reach the owner's own function or a fix to the SQL under `query` would leave
# the facade running the old one.
_RAW_READ_NAMES = (
    *_SORT_MODE_NAMES,
    ("get_data_extent", _RAW_READS, "get_data_extent"),
    ("get_event_breakdown", _RAW_READS, "get_event_breakdown"),
    ("get_filter_options", _RAW_READS, "get_filter_options"),
    ("get_issue_events", _RAW_READS, "get_issue_events"),
    ("get_issues", _RAW_READS, "get_issues"),
    ("get_recent_agent_exits", _RAW_READS, "get_recent_agent_exits"),
)

# The names each raw leaf publishes, grouped by the owner that defines them.
# The hub above the leaves republishes each projection and coercion under the
# same private spelling, so a caller reaching either the leaf or the hub lands
# on the one function the read families call.
_AGENT_EXIT_NAMES = (
    ("_agent_exit_from_row", _AGENT_EXITS, "agent_exit_from_row"),
    ("_recent_agent_exit_rows", _AGENT_EXITS, "recent_agent_exit_rows"),
)

_EVENT_BREAKDOWN_NAMES = (
    ("_event_breakdown_rows", _EVENT_BREAKDOWNS, "event_breakdown_rows"),
)

_FILTER_OPTION_NAMES = (
    ("_FILTER_OPTION_COLUMNS", _FILTER_OPTIONS, "FILTER_OPTION_COLUMNS"),
    ("_filter_options_from_rows", _FILTER_OPTIONS, "filter_options_from_rows"),
    ("_filter_options_sql", _FILTER_OPTIONS, "filter_options_sql"),
)

_ISSUE_EVENT_NAMES = (
    ("_issue_event_from_row", _ISSUE_EVENTS, "issue_event_from_row"),
    ("_issue_event_rows", _ISSUE_EVENTS, "issue_event_rows"),
)

_ISSUE_SUMMARY_NAMES = (
    ("_issue_order_sql", _ISSUE_SUMMARIES, "issue_order_sql"),
    ("_issue_summary_from_row", _ISSUE_SUMMARIES, "issue_summary_from_row"),
    ("_issue_summary_rows", _ISSUE_SUMMARIES, "issue_summary_rows"),
    ("_issues_sql", _ISSUE_SUMMARIES, "issues_sql"),
)

# The query rows are the one raw group the hub never published: they were only
# ever reached on this leaf, which is why it has to keep answering for them.
_QUERY_ROW_NAMES = (
    ("AgentExitQueryRow", _QUERY_ROWS, "AgentExitQueryRow"),
    ("IssueSummaryQueryRow", _QUERY_ROWS, "IssueSummaryQueryRow"),
    ("ReviewRoundQueryRow", _QUERY_ROWS, "ReviewRoundQueryRow"),
    ("agent_exit_row", _QUERY_ROWS, "agent_exit_row"),
    ("issue_summary_row", _QUERY_ROWS, "issue_summary_row"),
    ("review_round_row", _QUERY_ROWS, "review_round_row"),
)

_RAW_VALUE_NAMES = (
    ("_bool_or_none", _RAW_VALUES, "bool_or_none"),
    ("_empty_filter_selected", _RAW_VALUES, "empty_filter_selected"),
    ("_float_or_none", _RAW_VALUES, "float_or_none"),
    ("_int_or_none", _RAW_VALUES, "int_or_none"),
    ("_row_int", _RAW_VALUES, "row_int"),
)

# The seven rollup reads, named once and read by both checks below for the same
# reason as the raw six: a page calls one off the facade, and the call has to
# reach the owner's own function or a fix to the SQL under `query` would leave
# the facade running the old one.
_ROLLUP_READ_NAMES = (
    ("get_backend_efficiency", _ROLLUP_READS, "get_backend_efficiency"),
    ("get_kpi_prev", _ROLLUP_READS, "get_kpi_prev"),
    ("get_repo_breakdown", _ROLLUP_READS, "get_repo_breakdown"),
    ("get_stage_breakdown", _ROLLUP_READS, "get_stage_breakdown"),
    ("get_summary", _ROLLUP_READS, "get_summary"),
    ("get_throughput_breakdown", _ROLLUP_READS, "get_throughput_breakdown"),
    ("get_time_series", _ROLLUP_READS, "get_time_series"),
)

# The names each rollup leaf publishes, grouped by the owner that defines them.
# The hub above the leaves republishes every one under the same private
# spelling, so a caller reaching either the leaf or the hub lands on the one
# function the rollup families call.
_STAGE_BREAKDOWN_NAMES = (
    ("_stage_breakdown_from_row", _STAGE_BREAKDOWNS, "stage_breakdown_from_row"),
    ("_stage_breakdown_rows", _STAGE_BREAKDOWNS, "stage_breakdown_rows"),
    ("_stage_breakdown_sql", _STAGE_BREAKDOWNS, "stage_breakdown_sql"),
)

_BACKEND_EFFICIENCY_NAMES = (
    (
        "_backend_efficiency_from_row",
        _BACKEND_EFFICIENCY,
        "backend_efficiency_from_row",
    ),
    ("_backend_efficiency_rows", _BACKEND_EFFICIENCY, "backend_efficiency_rows"),
    ("_backend_efficiency_sql", _BACKEND_EFFICIENCY, "backend_efficiency_sql"),
)

_CACHE_SHARE_NAMES = (
    ("_ROLLUP_ALL_TOKENS_SQL", _CACHE_SHARES, "ROLLUP_ALL_TOKENS_SQL"),
    ("_ROLLUP_CACHE_FRACTION_SQL", _CACHE_SHARES, "ROLLUP_CACHE_FRACTION_SQL"),
    ("_ROLLUP_CACHE_TOKENS_SQL", _CACHE_SHARES, "ROLLUP_CACHE_TOKENS_SQL"),
)

_REPO_BREAKDOWN_NAMES = (
    ("_repo_breakdown_rows", _REPO_BREAKDOWNS, "repo_breakdown_rows"),
)

_THROUGHPUT_NAMES = (
    ("_THROUGHPUT_RESOLVED_STAGES", _THROUGHPUT_DAYS, "THROUGHPUT_RESOLVED_STAGES"),
    ("_selected_throughput_stages", _THROUGHPUT_DAYS, "selected_throughput_stages"),
    ("_throughput_from_row", _THROUGHPUT_DAYS, "throughput_from_row"),
    ("_throughput_rows", _THROUGHPUT_DAYS, "throughput_rows"),
)

_KPI_TOTAL_NAMES = (
    ("_kpi_prev_sql", _KPI_TOTALS, "kpi_prev_sql"),
    ("_kpi_prev_summary", _KPI_TOTALS, "kpi_prev_summary"),
)

_TIME_SERIES_NAMES = (
    ("_time_series_from_row", _TIME_SERIES, "time_series_from_row"),
    ("_time_series_rows", _TIME_SERIES, "time_series_rows"),
)

# The four breakdown reads, read by both checks below for the same reason as the
# raw six and the rollup seven, and the names each of their projection owners
# publishes. The review-round leaf published the token-share fragments too, and
# those sit beside the rollup ones under the shared owner.
_BREAKDOWN_READ_NAMES = (
    ("get_backend_daily_tokens", _BREAKDOWN_READS, "get_backend_daily_tokens"),
    ("get_cost_coverage", _BREAKDOWN_READS, "get_cost_coverage"),
    ("get_hourly_heatmap", _BREAKDOWN_READS, "get_hourly_heatmap"),
    (
        "get_review_round_breakdown",
        _BREAKDOWN_READS,
        "get_review_round_breakdown",
    ),
)

_AGENT_CACHE_SHARE_NAMES = (
    ("_AGENT_ALL_TOKENS_SQL", _CACHE_SHARES, "AGENT_ALL_TOKENS_SQL"),
    ("_AGENT_CACHE_FRACTION_SQL", _CACHE_SHARES, "AGENT_CACHE_FRACTION_SQL"),
    ("_AGENT_CACHE_TOKENS_SQL", _CACHE_SHARES, "AGENT_CACHE_TOKENS_SQL"),
)

_REVIEW_ROUND_NAMES = (
    ("_review_round_from_row", _REVIEW_ROUNDS, "review_round_from_row"),
    ("_review_round_rows", _REVIEW_ROUNDS, "review_round_rows"),
    ("_review_round_sql", _REVIEW_ROUNDS, "review_round_sql"),
)

_COST_COVERAGE_NAMES = (
    ("_cost_coverage_from_row", _COST_COVERAGE, "cost_coverage_from_row"),
    ("_cost_coverage_rows", _COST_COVERAGE, "cost_coverage_rows"),
)

_BACKEND_TOKEN_NAMES = (
    (
        "_backend_daily_token_rows",
        _BACKEND_TOKENS,
        "backend_daily_token_rows",
    ),
    (
        "_backend_daily_tokens_from_row",
        _BACKEND_TOKENS,
        "backend_daily_tokens_from_row",
    ),
)

_HOURLY_HEATMAP_NAMES = (
    ("_hourly_heatmap_from_row", _HOURLY_HEATMAPS, "hourly_heatmap_from_row"),
    ("_hourly_heatmap_rows", _HOURLY_HEATMAPS, "hourly_heatmap_rows"),
)

# The three skill reads, read by both checks below for the same reason as the
# families above them, and the names each of their owners publishes. The leaf
# that held the finished-run condition published it alone, and the key shapes
# split across the two owners that answer for them: the cohort and its two
# cells under the readings owner, the identity column offsets under the
# sessions one.
_SKILL_READ_NAMES = (
    ("get_skill_adoption", _SKILL_READS, "get_skill_adoption"),
    ("get_skill_trigger_matrix", _SKILL_READS, "get_skill_trigger_matrix"),
    ("get_skill_trigger_rates", _SKILL_READS, "get_skill_trigger_rates"),
)

_AGENT_EXIT_CONDITION_NAMES = (
    ("_AGENT_EXIT_CONDITION", _CONDITIONS, "AGENT_EXIT_CONDITION"),
)

_SKILL_VALUE_NAMES = (
    ("_as_skill_names", _SKILL_VALUES, "as_skill_names"),
    ("_label_or_unknown", _SKILL_VALUES, "label_or_unknown"),
    ("_row_label", _SKILL_VALUES, "row_label"),
    ("_skill_cohort", _SKILL_VALUES, "skill_cohort"),
    ("_skill_matrix_order_key", _SKILL_VALUES, "skill_matrix_order_key"),
)

_SKILL_KEY_NAMES = (
    ("_SESSION_ID_INDEX", _SKILL_SESSIONS, "SESSION_ID_INDEX"),
    ("_SESSION_RESUME_INDEX", _SKILL_SESSIONS, "SESSION_RESUME_INDEX"),
    ("_SESSION_ROW_INDEX", _SKILL_SESSIONS, "SESSION_ROW_INDEX"),
    ("_SkillAdoptionKey", _SKILL_VALUES, "SkillAdoptionKey"),
    ("_SkillCohort", _SKILL_VALUES, "SkillCohort"),
    ("_SkillMatrixKey", _SKILL_VALUES, "SkillMatrixKey"),
)

_SKILL_TRIGGER_RATE_NAMES = (
    (
        "_skill_trigger_rate_from_row",
        _SKILL_TRIGGER_RATES,
        "skill_trigger_rate_from_row",
    ),
    ("_skill_trigger_rate_rows", _SKILL_TRIGGER_RATES, "skill_trigger_rate_rows"),
    ("_skill_trigger_rate_sql", _SKILL_TRIGGER_RATES, "skill_trigger_rate_sql"),
)

# The two row caps, named apart from the groups they belong to because the
# dashboard hub published them beside its reads and the leaves beside their
# aggregates -- so both sites bind the one constant rather than a copy.
_SKILL_MATRIX_LIMIT_NAME = (
    "SKILL_MATRIX_ROW_LIMIT", _SKILL_MATRICES, "SKILL_MATRIX_ROW_LIMIT",
)

_SKILL_ADOPTION_LIMIT_NAME = (
    "SKILL_ADOPTION_ROW_LIMIT", _SKILL_ADOPTION, "SKILL_ADOPTION_ROW_LIMIT",
)

_SKILL_MATRIX_NAMES = (
    _SKILL_MATRIX_LIMIT_NAME,
    ("_SkillMatrixCounts", _SKILL_MATRICES, "SkillMatrixCounts"),
    ("_skill_catalog", _SKILL_MATRICES, "skill_catalog"),
    ("_skill_catalog_rows", _SKILL_MATRICES, "skill_catalog_rows"),
    ("_skill_run_rows", _SKILL_MATRICES, "skill_run_rows"),
    ("_skill_trigger_matrix_rows", _SKILL_MATRICES, "skill_trigger_matrix_rows"),
)

_SKILL_SESSION_NAMES = (
    ("_SessionEvidence", _SKILL_SESSIONS, "SessionEvidence"),
    ("_SkillWindowRun", _SKILL_SESSIONS, "SkillWindowRun"),
    ("_skill_history_rows", _SKILL_SESSIONS, "skill_history_rows"),
    ("_skill_session_evidence", _SKILL_SESSIONS, "skill_session_evidence"),
    ("_skill_session_key", _SKILL_SESSIONS, "skill_session_key"),
    ("_skill_window_run", _SKILL_SESSIONS, "skill_window_run"),
    ("_skill_window_rows", _SKILL_SESSIONS, "skill_window_rows"),
)

_SKILL_ADOPTION_NAMES = (
    _SKILL_ADOPTION_LIMIT_NAME,
    ("_SkillAdoption", _SKILL_ADOPTION, "SkillAdoption"),
    ("_skill_adoption_rows", _SKILL_ADOPTION, "skill_adoption_rows"),
)

_SUMMARY_QUERY_NAMES = (
    ("_build_summary_sql", _SUMMARY_QUERIES, "build_summary_sql"),
    ("_build_summary_where", _SUMMARY_QUERIES, "build_summary_where"),
    ("_query_summary_rows", _SUMMARY_QUERIES, "query_summary_rows"),
)

_SUMMARY_RESULT_NAMES = (
    ("_SUMMARY_TOTAL_FIELD_CASTS", _SUMMARY_RESULTS, "SUMMARY_TOTAL_FIELD_CASTS"),
    ("_ordered_summary_counts", _SUMMARY_RESULTS, "ordered_summary_counts"),
    ("_summary_count_order", _SUMMARY_RESULTS, "summary_count_order"),
    ("_summary_from_rows", _SUMMARY_RESULTS, "summary_from_rows"),
    ("_summary_total_values", _SUMMARY_RESULTS, "summary_total_values"),
    ("_summary_totals_row", _SUMMARY_RESULTS, "summary_totals_row"),
)

# The cell readings split across two owners: the three a rollup row is narrowed
# by, and the float coercion the raw owner answers for on both sides.
_ROW_CELL_NAMES = (
    ("_cost_cell", _ROW_CELLS, "cost_cell"),
    ("_day_value", _ROW_CELLS, "day_value"),
    ("_float_or_none", _RAW_VALUES, "float_or_none"),
    ("_row_value", _ROW_CELLS, "row_value"),
)

# The historical facade name a caller already imports, and the owner attribute
# it now resolves to. The underscored ones are the sharper half: a private name
# a caller reached through the facade is still a name it reached, so it has to
# keep answering -- with the owner's object, not a copy the facade kept.
_FORWARDED = MappingProxyType({
    "AnalyticsReadError": (_CONNECTIONS, "AnalyticsReadError"),
    "_close_quietly": (_CONNECTIONS, "close_quietly"),
    "_default_connect": (_CONNECTIONS, "default_connect"),
    "_default_persistent_connect": (_CONNECTIONS, "default_persistent_connect"),
    "_is_broken_connection_exc": (_CONNECTIONS, "is_broken_connection_exc"),
    "_thread_local": (_CONNECTION_CACHE, "thread_local"),
    "analytics_connection": (_CONNECTION_CACHE, "analytics_connection"),
    "close_thread_local_connection": (
        _CONNECTION_CACHE, "close_thread_local_connection",
    ),
    **{
        name: (owner_name, attribute)
        for name, owner_name, attribute in (
            *_MODEL_NAMES,
            *_RAW_READ_NAMES,
            *_ROLLUP_READ_NAMES,
            *_BREAKDOWN_READ_NAMES,
            *_SKILL_READ_NAMES,
        )
    },
})

# The names each flat leaf publishes, grouped by the owner that defines them.
# The hub above the leaves publishes the union of the three, so a caller
# reaching either a leaf or the hub lands on the same object.
_CONDITION_NAMES = (
    ("_agent_event_excluded", _CONDITIONS, "agent_event_excluded"),
    ("_append_where_condition", _CONDITIONS, "append_where_condition"),
    ("_prepend_where_condition", _CONDITIONS, "prepend_where_condition"),
)

_FILTER_NAMES = (
    ("_WhereBuilder", _FILTERS, "WhereBuilder"),
    ("_WindowFilters", _FILTERS, "WindowFilters"),
)

_PREDICATE_NAMES = (
    ("_DAILY_ROLLUP_VIEW", _PREDICATES, "DAILY_ROLLUP_VIEW"),
    ("_build_rollup_window_where", _PREDICATES, "build_rollup_window_where"),
    ("_build_view_window_where", _PREDICATES, "build_view_window_where"),
    ("_build_where", _PREDICATES, "build_where"),
    ("_build_window_where", _PREDICATES, "build_window_where"),
    ("_day_bound", _PREDICATES, "day_bound"),
)

# The flat modules a caller reaches an owner through, and what each name they
# publish resolves to. Same contract as the facade above: the predicate a
# caller builds here has to be the one the read families build, and the row it
# type-checks against the class they construct, or a fix under `query` would
# reach only half of the callers.
_FORWARDED_MODULES = MappingProxyType({
    "orchestrator.analytics.predicates": (
        *_CONDITION_NAMES,
        *_FILTER_NAMES,
        *_PREDICATE_NAMES,
    ),
    "orchestrator.analytics._predicate_conditions": _CONDITION_NAMES,
    "orchestrator.analytics._predicate_models": _FILTER_NAMES,
    "orchestrator.analytics._predicate_where": _PREDICATE_NAMES,
    "orchestrator.analytics.read_request": (
        ("FILTERED_READ_SIGNATURE", _REQUESTS, "FILTERED_READ_SIGNATURE"),
        ("HEATMAP_SIGNATURE", _REQUESTS, "HEATMAP_SIGNATURE"),
        ("ISSUE_EVENTS_SIGNATURE", _REQUESTS, "ISSUE_EVENTS_SIGNATURE"),
        ("ISSUES_SIGNATURE", _REQUESTS, "ISSUES_SIGNATURE"),
        ("LIMIT_FIELD", _REQUESTS, "LIMIT_FIELD"),
        ("LIMITED_READ_SIGNATURE", _REQUESTS, "LIMITED_READ_SIGNATURE"),
        ("RECENT_EXIT_LIMIT", _REQUESTS, "RECENT_EXIT_LIMIT"),
        ("RECENT_EXITS_SIGNATURE", _REQUESTS, "RECENT_EXITS_SIGNATURE"),
        ("SOURCE_READ_SIGNATURE", _REQUESTS, "SOURCE_READ_SIGNATURE"),
        ("bind_read_request", _REQUESTS, "bind_read_request"),
        ("resolve_read_query", _REQUESTS, "resolve_read_query"),
        ("window_filters", _REQUESTS, "window_filters"),
    ),
    "orchestrator.analytics.read_request_models": (
        ("ReadConnection", _REQUEST_MODELS, "ReadConnection"),
        ("ReadFilters", _REQUEST_MODELS, "ReadFilters"),
        ("ReadOptions", _REQUEST_MODELS, "ReadOptions"),
        ("ReadRequest", _REQUEST_MODELS, "ReadRequest"),
    ),
    "orchestrator.analytics.read_models": _MODEL_NAMES,
    "orchestrator.analytics.read_models_activity": _ACTIVITY_MODEL_NAMES,
    "orchestrator.analytics.read_models_core": _OVERVIEW_MODEL_NAMES,
    "orchestrator.analytics.read_models_cost": _COST_MODEL_NAMES,
    # The run family is the one flat module publishing more than its rows: the
    # `result` attribute name and the accessor installed under it are what the
    # trace row's historical field spelling is kept alive by.
    "orchestrator.analytics.read_models_runs": (
        *_RUN_MODEL_NAMES,
        ("RESULT_FIELD", _RUN_MODELS, "RESULT_FIELD"),
        ("public_event_result", _RUN_MODELS, "public_event_result"),
    ),
    "orchestrator.analytics.read_models_skills": _SKILL_MODEL_NAMES,
    # The raw hub published its projections and coercions under private names
    # while it owned them, so each is pinned here alongside the six reads: a
    # private name a caller already imported is still a name it imported. The
    # sort-mode set is the one spelling the hub aliased -- it published the
    # frozenset under a leading underscore the leaf never used.
    "orchestrator.analytics.read_raw": (
        *_RAW_READ_NAMES,
        ("_ISSUE_SORT_BY_OPTIONS", _ISSUE_SUMMARIES, "ISSUE_SORT_BY_OPTIONS"),
        *_AGENT_EXIT_NAMES,
        *_EVENT_BREAKDOWN_NAMES,
        *_FILTER_OPTION_NAMES,
        *_ISSUE_EVENT_NAMES,
        *_ISSUE_SUMMARY_NAMES,
        *_RAW_VALUE_NAMES,
    ),
    "orchestrator.analytics._read_agent_exits": _AGENT_EXIT_NAMES,
    "orchestrator.analytics._read_event_breakdown": _EVENT_BREAKDOWN_NAMES,
    "orchestrator.analytics._read_filter_options": _FILTER_OPTION_NAMES,
    "orchestrator.analytics._read_issue_events": _ISSUE_EVENT_NAMES,
    "orchestrator.analytics._read_issues": (
        *_SORT_MODE_NAMES,
        ("ISSUE_SORT_BY_OPTIONS", _ISSUE_SUMMARIES, "ISSUE_SORT_BY_OPTIONS"),
        *_ISSUE_SUMMARY_NAMES,
    ),
    "orchestrator.analytics._read_query_rows": _QUERY_ROW_NAMES,
    "orchestrator.analytics._read_raw_values": _RAW_VALUE_NAMES,
    # The rollup hub published every leaf name it imported, the projections it
    # called included, so the whole union is pinned here alongside the seven
    # reads.
    "orchestrator.analytics.read_rollup": (
        *_ROLLUP_READ_NAMES,
        *_BACKEND_EFFICIENCY_NAMES,
        *_CACHE_SHARE_NAMES,
        *_KPI_TOTAL_NAMES,
        *_REPO_BREAKDOWN_NAMES,
        *_ROW_CELL_NAMES,
        *_STAGE_BREAKDOWN_NAMES,
        *_SUMMARY_QUERY_NAMES,
        *_SUMMARY_RESULT_NAMES,
        *_THROUGHPUT_NAMES,
        *_TIME_SERIES_NAMES,
    ),
    "orchestrator.analytics._read_rollup_breakdowns": (
        *_BACKEND_EFFICIENCY_NAMES,
        *_STAGE_BREAKDOWN_NAMES,
    ),
    "orchestrator.analytics._read_rollup_cost_sql": _CACHE_SHARE_NAMES,
    "orchestrator.analytics._read_rollup_repo": (
        *_REPO_BREAKDOWN_NAMES,
        *_THROUGHPUT_NAMES,
    ),
    "orchestrator.analytics._read_rollup_series": (
        *_KPI_TOTAL_NAMES,
        *_TIME_SERIES_NAMES,
    ),
    "orchestrator.analytics._read_row_values": _ROW_CELL_NAMES,
    "orchestrator.analytics._read_summary_query": _SUMMARY_QUERY_NAMES,
    "orchestrator.analytics._read_summary_result": _SUMMARY_RESULT_NAMES,
    "orchestrator.analytics._read_dashboard_breakdowns": (
        *_BACKEND_TOKEN_NAMES,
        *_COST_COVERAGE_NAMES,
        *_HOURLY_HEATMAP_NAMES,
    ),
    "orchestrator.analytics._read_review_rounds": (
        *_AGENT_CACHE_SHARE_NAMES,
        *_REVIEW_ROUND_NAMES,
    ),
    # The dashboard hub published the union of both families it held -- the
    # seven reads, the projections beneath them, and the cost column a
    # dashboard row is narrowed by -- so the whole union is pinned here.
    "orchestrator.analytics.read_dashboard": (
        *_BREAKDOWN_READ_NAMES,
        *_SKILL_READ_NAMES,
        ("_backend_daily_token_rows", _BACKEND_TOKENS, "backend_daily_token_rows"),
        ("_cost_cell", _ROW_CELLS, "cost_cell"),
        ("_cost_coverage_rows", _COST_COVERAGE, "cost_coverage_rows"),
        ("_hourly_heatmap_rows", _HOURLY_HEATMAPS, "hourly_heatmap_rows"),
        ("_review_round_rows", _REVIEW_ROUNDS, "review_round_rows"),
        _SKILL_ADOPTION_LIMIT_NAME,
        ("_skill_adoption_rows", _SKILL_ADOPTION, "skill_adoption_rows"),
        _SKILL_MATRIX_LIMIT_NAME,
        (
            "_skill_trigger_matrix_rows",
            _SKILL_MATRICES,
            "skill_trigger_matrix_rows",
        ),
        ("_skill_trigger_rate_rows", _SKILL_TRIGGER_RATES, "skill_trigger_rate_rows"),
    ),
    "orchestrator.analytics._read_dashboard_sql": _AGENT_EXIT_CONDITION_NAMES,
    "orchestrator.analytics._read_skill_adoption": _SKILL_ADOPTION_NAMES,
    "orchestrator.analytics._read_skill_matrix": _SKILL_MATRIX_NAMES,
    "orchestrator.analytics._read_skill_sessions": _SKILL_SESSION_NAMES,
    "orchestrator.analytics._read_skill_trigger_rates": _SKILL_TRIGGER_RATE_NAMES,
    "orchestrator.analytics._read_skill_types": _SKILL_KEY_NAMES,
    "orchestrator.analytics._read_skill_values": _SKILL_VALUE_NAMES,
})


class ForwardedFacadeSurfaceTest(unittest.TestCase):
    """Every connection and result name the facade publishes is the owner's."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        facade = import_module(_READ_FACADE)
        for name, (owner_name, attribute) in _FORWARDED.items():
            with self.subTest(name=name):
                self.assertIs(
                    getattr(facade, name),
                    getattr(import_module(owner_name), attribute),
                )

    def test_the_facade_still_publishes_them(self) -> None:
        # The resolver answers `__all__` off its own inventory, so a name
        # dropped from the manifest would keep resolving by attribute access
        # while disappearing from a wildcard import.
        facade = import_module(_READ_FACADE)
        self.assertTrue(frozenset(_FORWARDED).issubset(facade.__all__))


class ForwardedFlatModuleTest(unittest.TestCase):
    """Every name the flat read modules publish is the owner's own object."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        for module_name, forwarded in _FORWARDED_MODULES.items():
            for name, owner_name, attribute in forwarded:
                with self.subTest(module=module_name, name=name):
                    self.assertIs(
                        getattr(import_module(module_name), name),
                        getattr(import_module(owner_name), attribute),
                    )

    def test_no_flat_module_defines_one_itself(self) -> None:
        # What keeps the forwarding thin: a module that defined a name of its
        # own would be a second implementation the check above cannot see,
        # because it only compares the names the module was asked for.
        for module_name in _FORWARDED_MODULES:
            defined = tuple(
                name
                for name, member in import_module(module_name).__dict__.items()
                if getattr(member, "__module__", None) == module_name
            )
            with self.subTest(module=module_name):
                self.assertEqual(defined, ())


if __name__ == "__main__":
    unittest.main()
