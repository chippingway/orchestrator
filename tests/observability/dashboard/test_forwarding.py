# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the flat dashboard modules still answer for once the owners hold it."""
from __future__ import annotations

import unittest
from importlib import import_module
from types import MappingProxyType

_THEME_FACADE = "orchestrator.dashboard_theme"

_STATE_HUB = "orchestrator.dashboard_state"

_READS_HUB = "orchestrator.dashboard_reads"

_KPI_SITE = "orchestrator.dashboard_kpis"

_KPI_STRIP_HUB = "orchestrator.dashboard_kpi_strip"

_KPI_SERIES_LEAF = "orchestrator._dashboard_kpi_series"

_KPI_VALUES_LEAF = "orchestrator._dashboard_kpi_values"

_CARD_HUB = "orchestrator.dashboard_cards"

_CARD_HEADERS_LEAF = "orchestrator._dashboard_card_headers"

_BACKEND_CARD_LEAF = "orchestrator._dashboard_backend_card"

_COVERAGE_CARD_LEAF = "orchestrator._dashboard_coverage_card"

_HTML_SURFACE = "orchestrator.dashboard_html"

_ISSUE_TABLE_LEAF = "orchestrator._dashboard_issue_table"

_READ_CORE_LEAF = "orchestrator._dashboard_read_core"

_DISPATCH_LEAF = "orchestrator._dashboard_read_dispatch"

_READ_MODE_LEAF = "orchestrator._dashboard_read_mode"

_BREAKDOWNS_LEAF = "orchestrator._dashboard_read_breakdowns"

_READ_PLAN_LEAF = "orchestrator._dashboard_read_plan"

_ROLLUPS_LEAF = "orchestrator._dashboard_read_rollups"

_SKILLS_LEAF = "orchestrator._dashboard_read_skills"

_SKILL_ADOPTION_HUB = "orchestrator.dashboard_skill_adoption"

_ADOPTION_COLUMNS_LEAF = "orchestrator._dashboard_adoption_columns"

_ADOPTION_HEADERS_LEAF = "orchestrator._dashboard_adoption_headers"

_ADOPTION_RENDER_LEAF = "orchestrator._dashboard_adoption_render"

_ADOPTION_ROWS_LEAF = "orchestrator._dashboard_adoption_rows"

_ADOPTION_SORT_LEAF = "orchestrator._dashboard_adoption_sort"

_SKILL_MATRIX_HUB = "orchestrator.dashboard_skill_matrix"

_MATRIX_COLUMNS_LEAF = "orchestrator._dashboard_matrix_columns"

_MATRIX_HEADERS_LEAF = "orchestrator._dashboard_matrix_headers"

_MATRIX_RENDER_LEAF = "orchestrator._dashboard_matrix_render"

_MATRIX_ROWS_LEAF = "orchestrator._dashboard_matrix_rows"

_MATRIX_SORT_LEAF = "orchestrator._dashboard_matrix_sort"

_SKILL_TRIGGER_TABLE_LEAF = "orchestrator._dashboard_skill_trigger_table"

_SPARKLINE_DATA_LEAF = "orchestrator._dashboard_sparkline_data"

_SPARKLINE_HTML_LEAF = "orchestrator._dashboard_sparkline_html"

_SUMMARY_HTML_LEAF = "orchestrator._dashboard_summary_html"

_DATE_CONTROLS_LEAF = "orchestrator._dashboard_date_widgets"

_DATE_FILTER_LEAF = "orchestrator._dashboard_date_range"

_TABLE_LEAF = "orchestrator._dashboard_table_html"

_DRILLDOWN_LEAF = "orchestrator._dashboard_drilldown"

_WIDGET_HUB = "orchestrator.dashboard_widgets"

_WIDGET_COSTS_LEAF = "orchestrator._dashboard_widget_costs"

_WIDGET_MODELS_LEAF = "orchestrator._dashboard_widget_models"

_WIDGET_RUNS_LEAF = "orchestrator._dashboard_widget_runs"

_WIDGET_SKILLS_LEAF = "orchestrator._dashboard_widget_skills"

_WIDGET_STATES_LEAF = "orchestrator._dashboard_widget_states"

_WIDGET_USAGE_LEAF = "orchestrator._dashboard_widget_usage"

# `from __future__ import annotations` opens every module in the repository and
# binds the compiler directive under a public name. It is a compilation
# instruction rather than something the theme answers for, so the surface check
# looks past it.
_FUTURE_DIRECTIVE = "annotations"

_PACKAGE = "orchestrator.observability.dashboard"

_ACTIVITY_PANEL = f"{_PACKAGE}.activity_panel"

_BACKEND_CARD = f"{_PACKAGE}.backend_card"

_BREAKDOWNS = f"{_PACKAGE}.breakdowns"

_CARD_HTML = f"{_PACKAGE}.card_html"

_COVERAGE_CARD = f"{_PACKAGE}.coverage_card"

_CSS = f"{_PACKAGE}.css"

_DATE_CONTROLS = f"{_PACKAGE}.date_controls"

_DATE_FILTER = f"{_PACKAGE}.date_filter"

_DISPATCH = f"{_PACKAGE}.dispatch"

_DRILLDOWN = f"{_PACKAGE}.drilldown"

_DRILLDOWN_REQUEST = f"{_PACKAGE}.drilldown_request"

_FANOUT = f"{_PACKAGE}.fanout"

_FILTER_BINDING = f"{_PACKAGE}.filter_binding"

_FILTERS = f"{_PACKAGE}.filters"

_FORMATTING = f"{_PACKAGE}.formatting"

_INSIGHTS = f"{_PACKAGE}.insights"

_ISSUE_COST_PANEL = f"{_PACKAGE}.issue_cost_panel"

_ISSUE_TABLE = f"{_PACKAGE}.issue_table"

_KPIS = f"{_PACKAGE}.kpis"

_KPI_SERIES = f"{_PACKAGE}.kpi_series"

_KPI_STRIP = f"{_PACKAGE}.kpi_strip"

_LAYOUT = f"{_PACKAGE}.layout"

_PAGE_MODELS = f"{_PACKAGE}.page_models"

_PAGE_STATES = f"{_PACKAGE}.page_states"

_PALETTE = f"{_PACKAGE}.palette"

_READ_MODE = f"{_PACKAGE}.read_mode"

_READ_PLAN = f"{_PACKAGE}.read_plan"

_RECENT_RUNS = f"{_PACKAGE}.recent_runs"

_RELIABILITY_PANEL = f"{_PACKAGE}.reliability_panel"

_RENDER_CONFIG = f"{_PACKAGE}.render_config"

_ROLLUPS = f"{_PACKAGE}.rollups"

_SCOPED_READS = f"{_PACKAGE}.scoped_reads"

_SKILL_ADOPTION = f"{_PACKAGE}.skill_adoption"

_SKILL_ADOPTION_COLUMNS = f"{_PACKAGE}.skill_adoption_columns"

_SKILL_ADOPTION_HEADERS = f"{_PACKAGE}.skill_adoption_headers"

_SKILL_ADOPTION_ROWS = f"{_PACKAGE}.skill_adoption_rows"

_SKILL_ADOPTION_SORT = f"{_PACKAGE}.skill_adoption_sort"

_SKILL_MATRIX = f"{_PACKAGE}.skill_matrix"

_SKILL_MATRIX_COLUMNS = f"{_PACKAGE}.skill_matrix_columns"

_SKILL_MATRIX_HEADERS = f"{_PACKAGE}.skill_matrix_headers"

_SKILL_MATRIX_ROWS = f"{_PACKAGE}.skill_matrix_rows"

_SKILL_MATRIX_SORT = f"{_PACKAGE}.skill_matrix_sort"

_SKILL_PANEL = f"{_PACKAGE}.skill_panel"

_SKILL_TRIGGER_PANEL = f"{_PACKAGE}.skill_trigger_panel"

_SKILL_TRIGGER_TABLE = f"{_PACKAGE}.skill_trigger_table"

_SKILLS = f"{_PACKAGE}.skills"

_SPARKLINE_HTML = f"{_PACKAGE}.sparkline_html"

_SPARKLINE_POINTS = f"{_PACKAGE}.sparkline_points"

_STAGE_COST_PANEL = f"{_PACKAGE}.stage_cost_panel"

_STATIC_METADATA = f"{_PACKAGE}.static_metadata"

_SUMMARY_HTML = f"{_PACKAGE}.summary_html"

_TABLES = f"{_PACKAGE}.tables"

_TOKENS = f"{_PACKAGE}.tokens"

_USAGE_PANEL = f"{_PACKAGE}.usage_panel"

_WINDOWS = f"{_PACKAGE}.windows"

# Every name a page reaches through `dashboard_theme`, and the owner it now
# resolves to. A color read here and the same color read off its owner have to
# be one object rather than two equal ones: the CSS variable the chrome is
# drawn from and the Plotly attribute a trace is drawn from are the same value
# seen twice, and a copy is where the two would start to disagree.
_FORWARDED = MappingProxyType({
    _PALETTE: (
        "ACCENT",
        "AGENT_ROLE_COLORS",
        "BACKEND_COLORS",
        "BACKGROUND",
        "BORDER",
        "CARD_BG",
        "CATEGORICAL_PALETTE",
        "COST_SOURCE_COLORS",
        "DANGER",
        "EVENT_COLORS",
        "GRID",
        "INK",
        "MUTED_TEXT",
        "MUTED_TEXT_SOFT",
        "NEUTRAL",
        "PRIMARY",
        "REVIEW_ROUND_COLORS",
        "SECONDARY",
        "STAGE_COLORS",
        "SUCCESS",
        "SURFACE",
        "TEXT",
        "TOKEN_TYPE_COLORS",
        "WARNING",
        "color_for",
    ),
    _TOKENS: (
        "CARD_PADDING",
        "CONTENT_MAX_WIDTH",
        "FONT_FAMILY",
        "FONT_SIZE",
        "GRID_GAP",
        "MONO_FONT_FAMILY",
        "RADIUS",
        "TITLE_FONT_SIZE",
        "TOPBAR_STICKY_HEIGHT",
    ),
    _LAYOUT: ("base_layout",),
    _CSS: ("PAGE_CSS",),
    _FORMATTING: (
        "fmt_money",
        "fmt_money_exact",
        "fmt_num",
        "fmt_tokens",
    ),
})

# The preset vocabulary, named once and read by both state checks below: the
# label a caller renders and the day count the window owner clamps by have to
# come off the same object, or the filter bar could offer a preset the
# arithmetic does not know.
_PRESET_NAMES = (
    ("DEFAULT_PRESET", _WINDOWS, "DEFAULT_PRESET"),
    ("DEFAULT_WINDOW_DAYS", _WINDOWS, "DEFAULT_WINDOW_DAYS"),
    ("PRESET_ALL", _WINDOWS, "PRESET_ALL"),
    ("PRESET_CUSTOM", _WINDOWS, "PRESET_CUSTOM"),
    ("PRESET_DAYS", _WINDOWS, "PRESET_DAYS"),
    ("PRESET_INLINE_LABELS", _WINDOWS, "PRESET_INLINE_LABELS"),
    ("PRESET_LABELS", _WINDOWS, "PRESET_LABELS"),
    ("PRESET_OPTIONS", _WINDOWS, "PRESET_OPTIONS"),
    ("PRESET_RECENT_THREE_DAYS", _WINDOWS, "PRESET_RECENT_THREE_DAYS"),
    ("PRESET_RECENT_WEEK", _WINDOWS, "PRESET_RECENT_WEEK"),
)

# The offset range the sidebar selector is drawn from, and beneath it the two
# bounds the range is built out of -- those only ever reached the leaf, so the
# hub is not asked for them.
_OFFSET_NAMES = (
    ("DEFAULT_TZ_OFFSET_HOURS", _FILTERS, "DEFAULT_TZ_OFFSET_HOURS"),
    ("TZ_OFFSET_OPTIONS", _FILTERS, "TZ_OFFSET_OPTIONS"),
)

_OFFSET_BOUND_NAMES = (
    ("MAX_UTC_OFFSET", _FILTERS, "MAX_UTC_OFFSET"),
    ("MIN_UTC_OFFSET", _FILTERS, "MIN_UTC_OFFSET"),
)

# The read-mode constants the page still names directly. These are the names
# that have to keep pointing at one knob and one refusal message rather than a
# copy each. The truthy set is listed apart because the two sites spell it
# differently: bare on the leaf, and under a leading underscore on the hub.
_READ_MODE_NAMES = (
    ("PARALLEL_READS_ENV", _READ_MODE, "PARALLEL_READS_ENV"),
    ("PARALLEL_READS_MAX_WORKERS", _READ_MODE, "PARALLEL_READS_MAX_WORKERS"),
    ("UNCONFIGURED_DB_MESSAGE", _READ_MODE, "UNCONFIGURED_DB_MESSAGE"),
)

_LEAF_TRUTHY_NAME = ("TRUTHY", _READ_MODE, "TRUTHY")

_HUB_TRUTHY_NAME = ("_TRUTHY", _READ_MODE, "TRUTHY")

# The read-mode helpers both flat sites publish. Each has to be the owner's own
# object rather than a wrapper around it: the switch a page load is issued
# under and the refusal it is stopped by are single decisions, and a copy on
# either site is where a page and the owner would start to answer differently.
_READ_MODE_HELPERS = (
    (
        "dashboard_parallel_reads_enabled",
        _READ_MODE,
        "dashboard_parallel_reads_enabled",
    ),
    ("db_unconfigured_message", _READ_MODE, "db_unconfigured_message"),
)

# The parse is the third helper, listed apart because the two sites spell it
# differently: bare on the leaf, and under a leading underscore on the hub --
# which also publishes the flag that parse bound while the owner imported, so
# what a page reads cannot become a second parse of the same knob.
_HUB_READ_MODE_HELPERS = (
    *_READ_MODE_HELPERS,
    ("DASHBOARD_PARALLEL_READS", _READ_MODE, "DASHBOARD_PARALLEL_READS"),
    ("_parse_parallel_reads_flag", _READ_MODE, "parse_parallel_reads_flag"),
)

_LEAF_READ_MODE_HELPERS = (
    *_READ_MODE_HELPERS,
    ("parse_parallel_reads_flag", _READ_MODE, "parse_parallel_reads_flag"),
)

# The dispatch a page's read waves are run through, and the alias one reader
# in a wave is spelled by. Both sites have to reach the one fan-out: a wave
# submitted through a copy would key its results the same way while running
# them under whatever cap that copy was written with.
_LEAF_FAN_OUT_NAMES = (
    ("NamedReader", _FANOUT, "NamedReader"),
    ("fan_out_reads", _FANOUT, "fan_out_reads"),
)

_HUB_FAN_OUT_NAME = ("_fan_out_reads", _FANOUT, "fan_out_reads")

# What one page load is staged by: the plan the caller carries between the two
# waves, the task each entry of a wave is built as, the two registries, and the
# key pair they are bound to. A page reaching a copy of the registries would
# stage its load out of adapters -- and under a cache TTL -- nobody else can
# change. The reader alias is the fan-out owner's, because the type a wave is
# made of belongs where a wave is run.
_READ_PLAN_NAMES = (
    ("_DashboardReadPlan", _READ_PLAN, "DashboardReadPlan"),
    ("_ReaderTask", _FANOUT, "NamedReader"),
    ("_build_read_keys", _READ_PLAN, "build_read_keys"),
    ("_first_wave_readers", _READ_PLAN, "first_wave_readers"),
    ("_second_wave_readers", _READ_PLAN, "second_wave_readers"),
    ("_widget_readers", _READ_PLAN, "widget_readers"),
    ("_widget_task", _READ_PLAN, "widget_task"),
)

# What drives that plan: the two-wave run, the wave dispatch and load line it
# is built from, the spinner it is opened under, the mapping a wave hands back,
# and the logger the line goes out on. Both flat sites spell these the same
# way. A page reaching a copy would answer a failed load with a banner nobody
# else can reword, and measure a completed one onto a logger no operator's
# `grep dashboard.load` is pointed at.
_DISPATCH_NAMES = (
    ("LOADING_INDICATOR_MESSAGE", _DISPATCH, "LOADING_INDICATOR_MESSAGE"),
    ("_ReadResults", _DISPATCH, "ReadResults"),
    ("_dispatch_reads", _DISPATCH, "dispatch_reads"),
    ("_log_dashboard_load", _DISPATCH, "log_dashboard_load"),
    ("_run_read_waves", _DISPATCH, "run_read_waves"),
    ("log", _DISPATCH, "log"),
)

# What every read behind a page load goes through, published privately by both
# flat sites and publicly by the owners. One socket per thread, one unpacking
# of a cache key, and one TTL are the point of each: a second copy of the scope
# would open a second connection per wave, and a second unpacking is how a
# widget ends up reading a window its key was not hashed from.
_READ_CORE_NAMES = (
    ("STATIC_METADATA_TTL_SECONDS", _STATIC_METADATA, "STATIC_METADATA_TTL_SECONDS"),
    ("_filter_list", _FILTER_BINDING, "filter_list"),
    ("_read_data_extent", _STATIC_METADATA, "read_data_extent"),
    ("_read_filter_kwargs", _FILTER_BINDING, "read_filter_kwargs"),
    ("_read_filter_options", _STATIC_METADATA, "read_filter_options"),
    ("_read_filtered", _FILTER_BINDING, "read_filtered"),
    ("_read_static_metadata", _STATIC_METADATA, "read_static_metadata"),
    ("_scoped_read", _SCOPED_READS, "scoped_read"),
)

# The seven headline and lifecycle reads, the cap the run list among them is
# read under, and the owner each resolves to. A page that reached a copy would
# draw its summary tiles, activity chart, stage table, run list, spend ranking,
# and review-round split from adapters nobody else can fix -- and could read a
# hundred-row cap the reliability tiles above that list were never sized for.
_ROLLUP_READ_NAMES = (
    ("DEFAULT_RECENT_AGENT_EXITS", _ROLLUPS, "DEFAULT_RECENT_AGENT_EXITS"),
    ("_read_prev_kpi", _ROLLUPS, "read_prev_kpi"),
    ("_read_recent_agent_exits", _ROLLUPS, "read_recent_agent_exits"),
    ("_read_review_round", _ROLLUPS, "read_review_round"),
    ("_read_stage_breakdown", _ROLLUPS, "read_stage_breakdown"),
    ("_read_summary", _ROLLUPS, "read_summary"),
    ("_read_time_series", _ROLLUPS, "read_time_series"),
    ("_read_top_cost_issues", _ROLLUPS, "read_top_cost_issues"),
)

# The six comparison-panel reads, and the owner each resolves to. A page that
# reached a copy would draw its backend, repository, coverage, heatmap,
# throughput, and daily-token sections from adapters nobody else can fix.
_BREAKDOWN_READ_NAMES = (
    ("_read_backend_daily_tokens", _BREAKDOWNS, "read_backend_daily_tokens"),
    ("_read_backend_efficiency", _BREAKDOWNS, "read_backend_efficiency"),
    ("_read_cost_coverage", _BREAKDOWNS, "read_cost_coverage"),
    ("_read_hourly_heatmap", _BREAKDOWNS, "read_hourly_heatmap"),
    ("_read_repo_breakdown", _BREAKDOWNS, "read_repo_breakdown"),
    ("_read_throughput", _BREAKDOWNS, "read_throughput"),
)

# The three skill-panel reads, listed by the leaf each is spelled on: the
# trigger rates have always been reached through the panel leaf beside the six,
# and the matrix and adoption cells through the leaf named for them. A page that
# reached a copy of any of the three would draw its adoption table and the two
# diagnostics beneath it from adapters nobody else can fix.
_SKILL_TRIGGER_RATES_NAME = (
    "_read_skill_trigger_rates", _SKILLS, "read_skill_trigger_rates",
)

_SKILL_LEAF_NAMES = (
    ("_read_skill_adoption", _SKILLS, "read_skill_adoption"),
    ("_read_skill_trigger_matrix", _SKILLS, "read_skill_trigger_matrix"),
)

# Everything the read hub publishes on an owner's behalf, in one list: the
# scope, binding, and metadata reads a widget's wrapper goes through, the
# sixteen panel reads that are the wrappers themselves, the plan that stages
# them into the two waves a load is drawn in, and the dispatch that drives
# both. It is the site the lazy `dashboard.<name>` surface resolves the whole
# read inventory through, so these names are what a historical caller still
# lands on. They are a resolution contract rather than a call path: a test that
# has to intercept one patches the owner it resolves to, because that is what
# the page itself reaches.
_FORWARDED_READS_HUB = (
    *_READ_CORE_NAMES,
    *_ROLLUP_READ_NAMES,
    *_BREAKDOWN_READ_NAMES,
    *_SKILL_LEAF_NAMES,
    *_READ_PLAN_NAMES,
    *_DISPATCH_NAMES,
    _SKILL_TRIGGER_RATES_NAME,
)

# The banner surface the KPI site publishes on the insight owner's behalf: the
# two bands a window is interrupted at, the spellings an unpriced run reaches
# the second one under, the line a crossing is rendered as, and the reading
# that raises it. A copy of any of them would be a page opening on thresholds
# nobody else can tune.
_FORWARDED_INSIGHTS = (
    (
        "FAILURE_RATE_BANNER_THRESHOLD",
        _INSIGHTS,
        "FAILURE_RATE_BANNER_THRESHOLD",
    ),
    ("InsightBanner", _INSIGHTS, "InsightBanner"),
    ("UNPRICED_COST_SOURCES", _INSIGHTS, "UNPRICED_COST_SOURCES"),
    ("UNPRICED_COVERAGE_THRESHOLD", _INSIGHTS, "UNPRICED_COVERAGE_THRESHOLD"),
    ("compute_insights", _INSIGHTS, "compute_insights"),
)

# The arithmetic published beside those banners: the delta a tile is annotated
# with, the reliability triples, the ranking a spend table is drawn in and the
# rows it is cut to, and the rework share with the buckets it counts. A page
# reaching a copy of the cap or the bucket set would rank and measure against
# numbers nobody else can change.
_FORWARDED_KPIS = (
    ("DEFAULT_EXPENSIVE_LIMIT", _KPIS, "DEFAULT_EXPENSIVE_LIMIT"),
    ("REWORK_BUCKETS", _KPIS, "REWORK_BUCKETS"),
    ("kpi_delta", _KPIS, "kpi_delta"),
    ("reliability_tile_data", _KPIS, "reliability_tile_data"),
    ("rework_totals", _KPIS, "rework_totals"),
    ("top_expensive_issues", _KPIS, "top_expensive_issues"),
)

# The card markup both flat card sites publish: the mark and title every panel
# is headed by, the banner stack a page opens with, and the reliability strip
# beneath its headline tiles. The leaf spells all three publicly and the hub
# privately, and each has to be the owner's own object -- a copy of the header
# on either site is a set of cards the stylesheet stops selecting, because what
# it selects them by is the hidden mark this markup writes.
_CARD_MARKUP_NAMES = (
    ("card_header_html", _CARD_HTML, "card_header_html"),
    ("insights_html", _CARD_HTML, "insights_html"),
    ("reliability_tiles_html", _CARD_HTML, "reliability_tiles_html"),
)

# The per-backend efficiency card, published by its own leaf: the builder the
# page renders one `st.markdown` per backend from, and the three readings and
# the divide-by-zero guard beneath it. A copy of the guard is a card that
# raises on the first window a backend barely ran in.
_BACKEND_CARD_NAMES = (
    ("BackendEfficiencyMetrics", _BACKEND_CARD, "BackendEfficiencyMetrics"),
    (
        "backend_efficiency_card_html",
        _BACKEND_CARD,
        "backend_efficiency_card_html",
    ),
    ("backend_efficiency_metrics", _BACKEND_CARD, "backend_efficiency_metrics"),
    ("safe_ratio", _BACKEND_CARD, "safe_ratio"),
)

# The cost-attribution coverage bar beside it: the bar itself, the segment pair
# a slice and its legend line are built as, the hue a source is recognized by,
# and the denominator the whole bar is sized against. A copy of that last one
# is a page whose bar and whose banners could disagree about how much of a
# window went unpriced.
_COVERAGE_CARD_NAMES = (
    ("CoverageSegment", _COVERAGE_CARD, "CoverageSegment"),
    ("cost_coverage_bar_html", _COVERAGE_CARD, "cost_coverage_bar_html"),
    ("cost_coverage_weights", _COVERAGE_CARD, "cost_coverage_weights"),
    ("cost_source_color", _COVERAGE_CARD, "cost_source_color"),
    ("coverage_segment", _COVERAGE_CARD, "coverage_segment"),
    ("coverage_segments", _COVERAGE_CARD, "coverage_segments"),
)

# The whole card surface as the hub publishes it, under the private spellings
# the page always imported them by: the markup owner's three, the backend
# card's four, and the coverage bar's six.
_HUB_CARD_NAMES = (
    ("_card_header_html", _CARD_HTML, "card_header_html"),
    ("_insights_html", _CARD_HTML, "insights_html"),
    ("_reliability_tiles_html", _CARD_HTML, "reliability_tiles_html"),
    *(
        (f"_{name}", owner, attribute)
        for name, owner, attribute in (
            *_BACKEND_CARD_NAMES, *_COVERAGE_CARD_NAMES,
        )
    ),
)

# The compact table four panels are drawn as, published under the same private
# spellings by the leaf and by the HTML surface above it. Both sites have to
# reach the one owner: a copy of the stylesheet is a panel that stops matching
# the ones beside it, and a copy of the dash would let one table report an
# unpriced amount as a cost of nothing.
_TABLE_NAMES = (
    ("_int_or_zero", _TABLES, "int_or_zero"),
    ("_money_or_dash", _TABLES, "money_or_dash"),
    ("_relative_width_pct", _TABLES, "relative_width_pct"),
    ("_short_repo_name", _TABLES, "short_repo_name"),
    ("_table_css", _TABLES, "table_css"),
    ("_table_head_html", _TABLES, "table_head_html"),
    ("_table_html", _TABLES, "table_html"),
)

# The first of those four panels: the readings one row is reduced to and the
# reduction itself, the tone a review round crosses into, the pill a row's run
# health is read off, the row those three are rendered as, and the ranking the
# rows are assembled into. The leaf and the HTML surface above it spell all six
# the same way. A page reaching a copy would size its bars against a maximum,
# and tone its rounds at a threshold, nobody else can change.
_ISSUE_TABLE_NAMES = (
    ("_IssueRowView", _ISSUE_TABLE, "IssueRowView"),
    ("_issue_row_view", _ISSUE_TABLE, "issue_row_view"),
    ("_issue_status_pill", _ISSUE_TABLE, "issue_status_pill"),
    ("_issue_table_row_html", _ISSUE_TABLE, "issue_table_row_html"),
    ("_issues_table_html", _ISSUE_TABLE, "issues_table_html"),
    ("_review_round_html", _ISSUE_TABLE, "review_round_html"),
)

# The columns the panel is headed by and the rules its bars and pills are
# painted from are the pair the two sites spell differently: bare on the leaf,
# and under a leading underscore on the surface.
_LEAF_ISSUE_TABLE_NAMES = (
    ("ISSUES_TABLE_COLUMNS", _ISSUE_TABLE, "ISSUES_TABLE_COLUMNS"),
    ("ISSUES_TABLE_EXTRA_CSS", _ISSUE_TABLE, "ISSUES_TABLE_EXTRA_CSS"),
    *_ISSUE_TABLE_NAMES,
)

_HTML_ISSUE_TABLE_NAMES = (
    ("_ISSUES_TABLE_COLUMNS", _ISSUE_TABLE, "ISSUES_TABLE_COLUMNS"),
    ("_ISSUES_TABLE_EXTRA_CSS", _ISSUE_TABLE, "ISSUES_TABLE_EXTRA_CSS"),
    *_ISSUE_TABLE_NAMES,
)

# The second of the four: the row one cohort's skill use is rendered as, and
# the panel the rows are assembled into. Both sites spell the pair the same
# way. A page reaching a copy would size its rate bars against a busiest cohort
# nobody else can change.
_SKILL_TRIGGER_TABLE_NAMES = (
    (
        "_skill_trigger_row_html",
        _SKILL_TRIGGER_TABLE,
        "skill_trigger_row_html",
    ),
    ("_skill_triggers_html", _SKILL_TRIGGER_TABLE, "skill_triggers_html"),
)

# The columns the panel is headed by, the rules its rate bars are painted from,
# and the label a cohort the sink named no role or backend for is read under.
# Those three are the ones the two sites spell differently: bare on the leaf,
# and under a leading underscore on the surface -- where the two skill matrices
# beside the panel read the label off, so all three tables bucket a missing
# category the same way.
_LEAF_SKILL_TRIGGER_NAMES = (
    ("SKILL_TRIGGERS_TABLE_COLUMNS", _SKILL_TRIGGER_TABLE, "SKILL_TRIGGERS_TABLE_COLUMNS"),
    ("SKILL_TRIGGERS_EXTRA_CSS", _SKILL_TRIGGER_TABLE, "SKILL_TRIGGERS_EXTRA_CSS"),
    ("UNKNOWN", _SKILL_TRIGGER_TABLE, "UNKNOWN"),
    *_SKILL_TRIGGER_TABLE_NAMES,
)

_HTML_SKILL_TRIGGER_NAMES = (
    ("_SKILL_TRIGGERS_TABLE_COLUMNS", _SKILL_TRIGGER_TABLE, "SKILL_TRIGGERS_TABLE_COLUMNS"),
    ("_SKILL_TRIGGERS_EXTRA_CSS", _SKILL_TRIGGER_TABLE, "SKILL_TRIGGERS_EXTRA_CSS"),
    ("_UNKNOWN", _SKILL_TRIGGER_TABLE, "UNKNOWN"),
    *_SKILL_TRIGGER_TABLE_NAMES,
)

# The last two of the four panels are the ones an operator can reorder, so each
# arrives across five owners with a leaf apiece and one hub above them. The
# third is the per-session adoption table. Its two query parameters are the
# sharpest copy in the set: a heading linking under one spelling while the
# parse reads another is a click that silently reopens the table in its default
# order.
_ADOPTION_PARAM_NAMES = (
    ("SKILL_ADOPTION_SORT_PARAM", _SKILL_ADOPTION_COLUMNS, "SKILL_ADOPTION_SORT_PARAM"),
    ("SKILL_ADOPTION_DIR_PARAM", _SKILL_ADOPTION_COLUMNS, "SKILL_ADOPTION_DIR_PARAM"),
)

# The vocabulary a parameter names a column out of: the column model, the nine
# columns, the counts among them a first click sorts down, and the key each is
# ordered by. A copy of the keys would be a header offering a sort the ordering
# does not run.
_ADOPTION_VOCABULARY_NAMES = (
    ("SkillAdoptionColumn", _SKILL_ADOPTION_COLUMNS, "SkillAdoptionColumn"),
    ("SKILL_ADOPTION_COLUMNS", _SKILL_ADOPTION_COLUMNS, "SKILL_ADOPTION_COLUMNS"),
    (
        "SKILL_ADOPTION_NUMERIC_KEYS",
        _SKILL_ADOPTION_COLUMNS,
        "SKILL_ADOPTION_NUMERIC_KEYS",
    ),
    ("SKILL_ADOPTION_SORT_KEYS", _SKILL_ADOPTION_COLUMNS, "SKILL_ADOPTION_SORT_KEYS"),
)

# The parse a clicked heading is read back through, the per-column ordering it
# selects, and the two-key default a table nobody sorted opens in.
_ADOPTION_SORT_NAMES = (
    ("parse_skill_adoption_sort", _SKILL_ADOPTION_SORT, "parse_skill_adoption_sort"),
    ("_sort_skill_adoption_rows", _SKILL_ADOPTION_SORT, "sort_skill_adoption_rows"),
    (
        "_default_sort_skill_adoption_rows",
        _SKILL_ADOPTION_SORT,
        "default_sort_skill_adoption_rows",
    ),
    (
        "_skill_adoption_default_sort_key",
        _SKILL_ADOPTION_SORT,
        "skill_adoption_default_sort_key",
    ),
)

# What one heading offers on a click, the link it is drawn as, and the header
# row they are assembled into.
_ADOPTION_HEADER_NAMES = (
    (
        "_skill_adoption_header_state",
        _SKILL_ADOPTION_HEADERS,
        "skill_adoption_header_state",
    ),
    (
        "_skill_adoption_header_cell",
        _SKILL_ADOPTION_HEADERS,
        "skill_adoption_header_cell",
    ),
    (
        "_skill_adoption_header_html",
        _SKILL_ADOPTION_HEADERS,
        "skill_adoption_header_html",
    ),
)

_ADOPTION_HEADER_STATE_NAME = (
    "SkillAdoptionHeaderState", _SKILL_ADOPTION_HEADERS, "SkillAdoptionHeaderState",
)

# The tone a quiet cell is drawn in, the count and rate readings drawn in it,
# the readings one cell is reduced to, and the row they are rendered as.
_ADOPTION_ROW_NAMES = (
    ("_muted_zero_html", _SKILL_ADOPTION_ROWS, "muted_zero_html"),
    ("_adoption_count_html", _SKILL_ADOPTION_ROWS, "adoption_count_html"),
    ("_adoption_rate_html", _SKILL_ADOPTION_ROWS, "adoption_rate_html"),
    ("_skill_adoption_row_view", _SKILL_ADOPTION_ROWS, "skill_adoption_row_view"),
    ("_skill_adoption_row_html", _SKILL_ADOPTION_ROWS, "skill_adoption_row_html"),
)

_ADOPTION_ROW_VIEW_NAME = (
    "SkillAdoptionRowView", _SKILL_ADOPTION_ROWS, "SkillAdoptionRowView",
)

# The notice a window with no session evidence renders instead, and the sorted
# panel every other window is drawn as.
_ADOPTION_PANEL_NAMES = (
    ("SKILL_ADOPTION_EMPTY_MESSAGE", _SKILL_ADOPTION, "SKILL_ADOPTION_EMPTY_MESSAGE"),
    ("_skill_adoption_html", _SKILL_ADOPTION, "skill_adoption_html"),
)

_ADOPTION_CSS_NAME = (
    "SKILL_ADOPTION_EXTRA_CSS", _SKILL_ADOPTION, "SKILL_ADOPTION_EXTRA_CSS",
)

# The whole adoption surface as the hub publishes it: the seven names the
# leaves spell bare take a leading underscore there, which is how the page
# always imported them.
_HUB_SKILL_ADOPTION_NAMES = (
    *_ADOPTION_PARAM_NAMES,
    *_ADOPTION_SORT_NAMES,
    *_ADOPTION_HEADER_NAMES,
    *_ADOPTION_ROW_NAMES,
    *_ADOPTION_PANEL_NAMES,
    *(
        (f"_{name}", owner, attribute)
        for name, owner, attribute in (
            *_ADOPTION_VOCABULARY_NAMES,
            _ADOPTION_HEADER_STATE_NAME,
            _ADOPTION_ROW_VIEW_NAME,
            _ADOPTION_CSS_NAME,
        )
    ),
)

# The fourth is the invocation-level trigger matrix, split the same way and
# carrying its own pair of parameters so a click on either table leaves the
# other's order alone.
_MATRIX_PARAM_NAMES = (
    ("SKILL_MATRIX_SORT_PARAM", _SKILL_MATRIX_COLUMNS, "SKILL_MATRIX_SORT_PARAM"),
    ("SKILL_MATRIX_DIR_PARAM", _SKILL_MATRIX_COLUMNS, "SKILL_MATRIX_DIR_PARAM"),
)

# The vocabulary a parameter names a column out of: the column model, the seven
# columns, the counts among them a first click sorts down, and the key each is
# ordered by. A copy of the keys would be a header offering a sort the ordering
# does not run.
_MATRIX_VOCABULARY_NAMES = (
    ("SkillMatrixColumn", _SKILL_MATRIX_COLUMNS, "SkillMatrixColumn"),
    ("SKILL_MATRIX_COLUMNS", _SKILL_MATRIX_COLUMNS, "SKILL_MATRIX_COLUMNS"),
    ("SKILL_MATRIX_NUMERIC_KEYS", _SKILL_MATRIX_COLUMNS, "SKILL_MATRIX_NUMERIC_KEYS"),
    ("SKILL_MATRIX_SORT_KEYS", _SKILL_MATRIX_COLUMNS, "SKILL_MATRIX_SORT_KEYS"),
)

# The parse a clicked heading is read back through, the per-column ordering it
# selects, and the two-key default a matrix nobody sorted opens in.
_MATRIX_SORT_NAMES = (
    ("parse_skill_matrix_sort", _SKILL_MATRIX_SORT, "parse_skill_matrix_sort"),
    ("_sort_skill_matrix_rows", _SKILL_MATRIX_SORT, "sort_skill_matrix_rows"),
    (
        "_default_sort_skill_matrix_rows",
        _SKILL_MATRIX_SORT,
        "default_sort_skill_matrix_rows",
    ),
    (
        "_skill_matrix_default_sort_key",
        _SKILL_MATRIX_SORT,
        "skill_matrix_default_sort_key",
    ),
)

# What one heading offers on a click, the link it is drawn as, and the header
# row they are assembled into.
_MATRIX_HEADER_NAMES = (
    ("_skill_matrix_header_state", _SKILL_MATRIX_HEADERS, "skill_matrix_header_state"),
    ("_skill_matrix_header_cell", _SKILL_MATRIX_HEADERS, "skill_matrix_header_cell"),
    ("_skill_matrix_header_html", _SKILL_MATRIX_HEADERS, "skill_matrix_header_html"),
)

_MATRIX_HEADER_STATE_NAME = (
    "SkillMatrixHeaderState", _SKILL_MATRIX_HEADERS, "SkillMatrixHeaderState",
)

# The tone a quiet cell is drawn in, the readings one cell is reduced to, and
# the row they are rendered as.
_MATRIX_ROW_NAMES = (
    ("_muted_zero_html", _SKILL_MATRIX_ROWS, "muted_zero_html"),
    ("_skill_matrix_row_view", _SKILL_MATRIX_ROWS, "skill_matrix_row_view"),
    ("_skill_matrix_row_html", _SKILL_MATRIX_ROWS, "skill_matrix_row_html"),
)

_MATRIX_ROW_VIEW_NAME = (
    "SkillMatrixRowView", _SKILL_MATRIX_ROWS, "SkillMatrixRowView",
)

# The notice a window with no catalog-backed cell renders instead, and the
# sorted panel every other window is drawn as.
_MATRIX_PANEL_NAMES = (
    ("SKILL_MATRIX_EMPTY_MESSAGE", _SKILL_MATRIX, "SKILL_MATRIX_EMPTY_MESSAGE"),
    ("_skill_matrix_html", _SKILL_MATRIX, "skill_matrix_html"),
)

_MATRIX_CSS_NAME = (
    "SKILL_MATRIX_EXTRA_CSS", _SKILL_MATRIX, "SKILL_MATRIX_EXTRA_CSS",
)

# The whole matrix surface as the hub publishes it: the seven names the leaves
# spell bare take a leading underscore there, which is how the page always
# imported them.
_HUB_SKILL_MATRIX_NAMES = (
    *_MATRIX_PARAM_NAMES,
    *_MATRIX_SORT_NAMES,
    *_MATRIX_HEADER_NAMES,
    *_MATRIX_ROW_NAMES,
    *_MATRIX_PANEL_NAMES,
    *(
        (f"_{name}", owner, attribute)
        for name, owner, attribute in (
            *_MATRIX_VOCABULARY_NAMES,
            _MATRIX_HEADER_STATE_NAME,
            _MATRIX_ROW_VIEW_NAME,
            _MATRIX_CSS_NAME,
        )
    ),
)

# The notice a window with no `agent_exit` row is answered with, spelled once
# because three owners under the package publish it under this one public name.
_NO_AGENT_EXITS = "NO_AGENT_EXITS_MESSAGE"

# The two cards those three skill tables are reported on, and the caption the
# first of them qualifies a quiet window with. The page draws only the adoption
# card, so the trigger-rate pair beside it is what a caller reaching past the
# page still lands on -- and both have to be the owners' own objects, or the
# panel an operator reads and the one a fix under the owner reaches would be
# two different renders of the same window.
_SKILL_PANEL_NAMES = (
    (_NO_AGENT_EXITS, _SKILL_TRIGGER_PANEL, _NO_AGENT_EXITS),
    ("_render_skill_adoption", _SKILL_PANEL, "render_skill_adoption"),
    (
        "_render_skill_invocation_diagnostics",
        _SKILL_PANEL,
        "render_skill_invocation_diagnostics",
    ),
    (
        "_render_skill_matrix_expander",
        _SKILL_TRIGGER_PANEL,
        "render_skill_matrix_expander",
    ),
    ("_render_skill_triggers", _SKILL_TRIGGER_PANEL, "render_skill_triggers"),
    (
        "_skill_adoption_evidence_caption",
        _SKILL_PANEL,
        "skill_adoption_evidence_caption",
    ),
    (
        "_skill_adoption_zero_caption",
        _SKILL_PANEL,
        "skill_adoption_zero_caption",
    ),
)

# The card above every one of those panels, and the toggle deciding what it
# stacks: the render itself, the label and index one mode is offered and seeded
# by, and the per-day totals the backend stack is drawn from. The label and the
# index are the same choice read from two ends -- what the option says and
# where it sits -- so a copy of either is a toggle that opens on a mode other
# than the one it names.
_USAGE_PANEL_NAMES = (
    ("_backend_tokens_by_day", _USAGE_PANEL, "backend_tokens_by_day"),
    ("_render_hero_usage", _USAGE_PANEL, "render_hero_usage"),
    ("_stack_mode_index", _USAGE_PANEL, "stack_mode_index"),
    ("_stack_mode_label", _USAGE_PANEL, "stack_mode_label"),
)

# The seven shapes one render is threaded through, as the widget leaf still
# publishes them: the caller's module handles, the selections every read is
# narrowed by, the controls and the page they open on, the headline numbers a
# load answers with, that load itself, and the four reads one comparison panel
# is drawn from. Each has to be the owner's own class rather than a copy --
# the pipeline builds a page in one module and is handed it in another, so two
# classes with the same fields are two windows a section could be drawn under.
_PAGE_STATE_NAMES = (
    ("_DashboardControls", _PAGE_MODELS, "DashboardControls"),
    ("_DashboardFilters", _PAGE_MODELS, "DashboardFilters"),
    ("_DashboardKpis", _PAGE_MODELS, "DashboardKpis"),
    ("_DashboardModules", _PAGE_MODELS, "DashboardModules"),
    ("_DashboardPage", _PAGE_MODELS, "DashboardPage"),
    ("_LoadedDashboard", _PAGE_MODELS, "LoadedDashboard"),
    ("_ReliabilityPanelData", _PAGE_MODELS, "ReliabilityPanelData"),
)

# The two sections a window's spend is compared across, as the widget leaf
# still publishes them: the paired lifecycle bars with the height both are
# pinned to and the two measurements that height is built from, and the ranked
# issues beside the backends that ran them, with the notice those backend cards
# answer a window carrying no run with. The height is forwarded rather than
# recomputed because a copy is two panels sized apart, which is the one thing
# drawing them side by side exists to prevent.
_COST_PANEL_NAMES = (
    (_NO_AGENT_EXITS, _ISSUE_COST_PANEL, _NO_AGENT_EXITS),
    ("_TABLE_BASE_HEIGHT", _STAGE_COST_PANEL, "TABLE_BASE_HEIGHT"),
    ("_TABLE_ROW_HEIGHT", _STAGE_COST_PANEL, "TABLE_ROW_HEIGHT"),
    ("_paired_bars_height", _STAGE_COST_PANEL, "paired_bars_height"),
    (
        "_render_issues_and_backends",
        _ISSUE_COST_PANEL,
        "render_issues_and_backends",
    ),
    (
        "_render_stage_review_bars",
        _STAGE_COST_PANEL,
        "render_stage_review_bars",
    ),
)

# The third section beneath those two, as the same leaf publishes it: a
# window's repository ranking beside the tiles and days its runs are read for.
_RELIABILITY_PANEL_NAMES = (
    (
        "_render_repo_and_reliability",
        _RELIABILITY_PANEL,
        "render_repo_and_reliability",
    ),
)

# The card that leaf closes on, beneath all three: the weekday-by-hour grid the
# window's tokens are laid out on.
_ACTIVITY_PANEL_NAMES = (
    (
        "_render_activity_heatmap",
        _ACTIVITY_PANEL,
        "render_activity_heatmap",
    ),
)

# The run listing at the foot of the page and the per-issue trace under it, as
# the widget leaf still publishes them: the expander a window's runs are drawn
# in, the notice a window with none renders instead, and the section an
# operator opens on one of those runs. The render has to be the owner's own
# object -- the page renderers are resolved through the facade at call time, so
# a copy here is a section a fix under the owner would never reach.
_RUN_SECTION_NAMES = (
    (_NO_AGENT_EXITS, _RECENT_RUNS, _NO_AGENT_EXITS),
    ("_render_drilldown_view", _DRILLDOWN, "render_drilldown_view"),
    ("_render_recent_runs", _RECENT_RUNS, "render_recent_runs"),
)

# The typed request and the adapter in front of it, as the flat site the facade
# exports the drill-down's historical call shape from still publishes them.
_DRILLDOWN_CALL_NAMES = (
    ("_DrilldownRequest", _DRILLDOWN_REQUEST, "DrilldownRequest"),
    ("_render_drilldown", _DRILLDOWN_REQUEST, "render_drilldown"),
)

# The two states a page leaves through and the line it ends on, as the widget
# leaf still publishes them: the startup state a database nobody has ingested
# into is answered with, the notice a window matching no row renders, the
# footer beneath a page that did draw, and the two messages the first two say
# it in. The renders are reached through the facade at call time, so a copy
# here is a banner or a footer a fix under the owner would never reach.
_PAGE_END_NAMES = (
    ("EMPTY_WINDOW_MESSAGE", _PAGE_STATES, "EMPTY_WINDOW_MESSAGE"),
    ("NO_DATA_MESSAGE", _PAGE_STATES, "NO_DATA_MESSAGE"),
    (
        "_render_dashboard_footer",
        _PAGE_STATES,
        "render_dashboard_footer",
    ),
    ("_render_empty_window", _PAGE_STATES, "render_empty_window"),
    ("_render_no_data", _PAGE_STATES, "render_no_data"),
)

# What the widget hub above those leaves publishes on an owner's behalf: those
# seven, the six the cost sections are drawn and sized by, the pair and the
# grid beneath them, the per-issue trace under the run listing, the two states
# the page leaves through with the line it ends on, and the Plotly
# defaults every figure the page draws is handed. A copy of the defaults is a
# panel whose hover toolbar nobody switched off, and this
# is the alias a caller reaching past the owners still reads them off, so what
# a test patches here and what the owner holds have to be one object.
_WIDGET_HUB_NAMES = (
    *_PAGE_STATE_NAMES,
    *_COST_PANEL_NAMES,
    *_RELIABILITY_PANEL_NAMES,
    *_ACTIVITY_PANEL_NAMES,
    *_PAGE_END_NAMES,
    ("_render_drilldown_view", _DRILLDOWN, "render_drilldown_view"),
    ("PLOTLY_CONFIG", _RENDER_CONFIG, "PLOTLY_CONFIG"),
)

# The per-day lines drawn under three of those tiles, and the two reductions
# the tiles themselves are totalled by. A second token total is the sharpest
# copy here: a window counts all four token columns, so a line reduced anywhere
# but the owner is one that could sit below its own headline.
_FORWARDED_KPI_SERIES = (
    ("_DailyKpiSeries", _KPI_SERIES, "DailyKpiSeries"),
    ("_daily_kpi_series", _KPI_SERIES, "daily_kpi_series"),
    ("_daily_point_totals", _KPI_SERIES, "daily_point_totals"),
    ("_summary_total_tokens", _KPI_SERIES, "summary_total_tokens"),
    ("_throughput_totals", _KPI_SERIES, "throughput_totals"),
    ("_time_series_total_tokens", _KPI_SERIES, "time_series_total_tokens"),
)

# The strip those lines are drawn inside: what one is built from, the scalars a
# window is reduced to, the four entries, and the build the widget pipeline
# calls. The build is the one the page renders the strip out of, so a copy here
# would be four tiles an operator reads that no fix under the owner reaches.
_FORWARDED_KPI_TILES = (
    ("_KpiInputs", _KPI_STRIP, "KpiInputs"),
    ("_KpiStripData", _KPI_STRIP, "KpiStripData"),
    ("_KpiTotals", _KPI_STRIP, "KpiTotals"),
    ("_build_kpi_strip_data", _KPI_STRIP, "build_kpi_strip_data"),
    ("_cost_per_resolved", _KPI_STRIP, "cost_per_resolved"),
    ("_kpi_strip_entries", _KPI_STRIP, "kpi_strip_entries"),
    ("_kpi_totals", _KPI_STRIP, "kpi_totals"),
)

# The keys one entry is read back by, listed apart because only the leaf ever
# published them: the strip's HTML builder looks a tile up under each, so the
# names it writes and the names that builder reads have to be one set.
_KPI_ENTRY_KEYS = (
    ("_DELTA_KEY", _KPI_STRIP, "_DELTA_KEY"),
    ("_LABEL_KEY", _KPI_STRIP, "_LABEL_KEY"),
    ("_SPARK_KEY", _KPI_STRIP, "_SPARK_KEY"),
    ("_SUBTITLE_KEY", _KPI_STRIP, "_SUBTITLE_KEY"),
    ("_VALUE_KEY", _KPI_STRIP, "_VALUE_KEY"),
)

# Where one of those lines puts each day it is drawn from: the floor a flat
# window's span is clamped at, the anchoring a window is projected through, and
# the placement itself. The projection leaf and the HTML surface above it spell
# all seven the same way. A page reaching a copy of the floor would scale a
# quiet window against a range nobody else can widen.
_SPARKLINE_POINT_NAMES = (
    ("_EPSILON", _SPARKLINE_POINTS, "EPSILON"),
    ("_SparklineLayout", _SPARKLINE_POINTS, "SparklineLayout"),
    ("_sparkline_layout", _SPARKLINE_POINTS, "sparkline_layout"),
    ("_sparkline_point", _SPARKLINE_POINTS, "sparkline_point"),
    ("_sparkline_points", _SPARKLINE_POINTS, "sparkline_points"),
    ("_sparkline_step", _SPARKLINE_POINTS, "sparkline_step"),
    ("_sparkline_y", _SPARKLINE_POINTS, "sparkline_y"),
)

# The pair of path strings a projected window is written as, listed apart
# because the projection leaf publishes it while the rendering owner beside it
# is where both are built.
_SPARKLINE_PATHS_NAME = ("_SparklinePaths", _SPARKLINE_HTML, "SparklinePaths")

# The markup those points reach a tile as: the two paths, the rounding they
# share, and the render the strip calls. All four are spelled the same way by
# the rendering leaf and the HTML surface above it. A copy of the rounding is a
# fill tracing days the line above it does not.
_SPARKLINE_MARKUP_NAMES = (
    ("_sparkline_area_path", _SPARKLINE_HTML, "sparkline_area_path"),
    ("_sparkline_paths", _SPARKLINE_HTML, "sparkline_paths"),
    ("_sparkline_point_text", _SPARKLINE_HTML, "sparkline_point_text"),
    ("_sparkline_svg", _SPARKLINE_HTML, "sparkline_svg"),
)

# What only the rendering leaf published: the box a tile draws a line in when
# a caller names none, the request one line is described by, the renderer the
# keyword surface applies onto, and that surface itself. A copy of the
# signature is a call spelled the way every caller spells it that binds to
# nothing.
_LEAF_SPARKLINE_NAMES = (
    ("DEFAULT_SPARKLINE_HEIGHT", _SPARKLINE_HTML, "DEFAULT_SPARKLINE_HEIGHT"),
    ("DEFAULT_SPARKLINE_WIDTH", _SPARKLINE_HTML, "DEFAULT_SPARKLINE_WIDTH"),
    ("_SPARKLINE_SIGNATURE", _SPARKLINE_HTML, "SPARKLINE_SIGNATURE"),
    ("_SparklineRequest", _SPARKLINE_HTML, "SparklineRequest"),
    ("_render_sparkline", _SPARKLINE_HTML, "render_sparkline"),
    *_SPARKLINE_MARKUP_NAMES,
)

# The band those tiles sit in: the banner above the strip, the line under the
# filter bar, the pill one tile's move is annotated with, the strip itself, and
# the suffix the first two count their repos and days by. The chrome leaf and
# the HTML surface above it spell all five the same way. A copy of the pill is
# a strip whose tiles could paint a rise two ways.
_SUMMARY_MARKUP_NAMES = (
    ("_delta_pill", _SUMMARY_HTML, "delta_pill"),
    ("_filter_meta_html", _SUMMARY_HTML, "filter_meta_html"),
    ("_kpi_strip_html", _SUMMARY_HTML, "kpi_strip_html"),
    ("_plural_s", _SUMMARY_HTML, "plural_s"),
    ("_topbar_html", _SUMMARY_HTML, "topbar_html"),
)

# What only the chrome leaf published: the tone and arrow a move is painted
# from, the request the banner is described by, and the two bound keyword
# surfaces. A copy of either signature is a call spelled the way every caller
# spells it that binds to nothing.
_LEAF_SUMMARY_NAMES = (
    ("_DELTA_SIGNATURE", _SUMMARY_HTML, "DELTA_SIGNATURE"),
    ("_TOPBAR_SIGNATURE", _SUMMARY_HTML, "TOPBAR_SIGNATURE"),
    ("_TopbarRequest", _SUMMARY_HTML, "TopbarRequest"),
    ("_delta_style", _SUMMARY_HTML, "delta_style"),
    *_SUMMARY_MARKUP_NAMES,
)

# The bar that window is picked in, split across the slot it is laid out in
# and the round trip drawn inside it. The two leaves spell all eight the same
# way. A copy of the slots is a bar whose label, presets, and pickers could be
# laid out in one module and filled in another; a copy of the round trip is a
# window an operator typed into that no read below is bounded by.
_DATE_CONTROL_NAMES = (
    ("_DateFilterColumns", _DATE_CONTROLS, "DateFilterColumns"),
    ("_date_filter_columns", _DATE_CONTROLS, "date_filter_columns"),
    ("_preset_radio_index", _DATE_CONTROLS, "preset_radio_index"),
    ("_render_date_filter_label", _DATE_CONTROLS, "render_date_filter_label"),
    ("_render_preset_choice", _DATE_CONTROLS, "render_preset_choice"),
)

_DATE_FILTER_NAMES = (
    ("_initial_filter_window", _DATE_FILTER, "initial_filter_window"),
    ("_render_date_filter_bar", _DATE_FILTER, "render_date_filter_bar"),
    ("_render_date_inputs", _DATE_FILTER, "render_date_inputs"),
)

_WINDOW_NAMES = (
    ("DateWindow", _WINDOWS, "DateWindow"),
    ("default_date_range", _WINDOWS, "default_date_range"),
    ("preset_window", _WINDOWS, "preset_window"),
    ("previous_window", _WINDOWS, "previous_window"),
    ("to_window", _WINDOWS, "to_window"),
)

# The bounding-day read is the other name the two sites spell differently.
_LEAF_EXTENT_NAME = ("extent_dates", _WINDOWS, "extent_dates")

_HUB_EXTENT_NAME = ("_extent_dates", _WINDOWS, "extent_dates")

_FILTER_NAMES = (
    ("DashboardCacheKey", _FILTERS, "DashboardCacheKey"),
    ("cache_key", _FILTERS, "cache_key"),
    ("format_tz_offset", _FILTERS, "format_tz_offset"),
    ("parse_issue_number", _FILTERS, "parse_issue_number"),
    ("resolve_stage_filter", _FILTERS, "resolve_stage_filter"),
    ("shift_ts", _FILTERS, "shift_ts"),
)

# The flat modules a caller reaches one of these owners through, and what each
# name they publish resolves to: a window built here has to be the one the
# reads are bounded by, a key hashed here the one the cached reads are stored
# under, a scope entered here the one they all share, a panel read issued here
# the one a page draws that panel from, a wave staged here the one the load
# actually runs, a load driven here the one the operator's log line comes off,
# a KPI computed here the one every tile reports, a strip assembled here the one
# the page opens with, a card headed, weighed, or sized here the one the
# stylesheet paints, a table drawn here the one every hand-rolled panel is,
# a window's issues ranked here the ones the page lists, a cohort's skill
# use reported here the rate the panel beneath them shows, an adoption
# table or a matrix headed, ordered, projected, or assembled here the one an
# operator's click reorders, a window's days placed or written here the
# line a tile above them carries, a window bannered, restated, or annotated
# here the chrome that strip of tiles sits in, a bar laid out or a window
# picked here the one every read is bounded by, a skill card rendered here
# the one an operator reads three of those tables on, a hero card drawn or a
# stack mode offered here the one the page opens with, a window's spend
# compared or its hours laid out here the four sections beneath that card,
# a page threaded here
# the one every section is handed, a run listed or an issue traced here
# the section the page ends on, and an empty database, an empty window, or a
# drawn page signed off here the state that page leaves through,
# or a fix under the owners would reach only half of the callers.
_FORWARDED_MODULES = MappingProxyType({
    "orchestrator._dashboard_state_constants": (
        *_PRESET_NAMES,
        *_OFFSET_NAMES,
        *_OFFSET_BOUND_NAMES,
        *_READ_MODE_NAMES,
        _LEAF_TRUTHY_NAME,
    ),
    "orchestrator._dashboard_windows": (*_WINDOW_NAMES, _LEAF_EXTENT_NAME),
    "orchestrator._dashboard_filter_state": _FILTER_NAMES,
    _DATE_CONTROLS_LEAF: _DATE_CONTROL_NAMES,
    _DATE_FILTER_LEAF: _DATE_FILTER_NAMES,
    _READ_CORE_LEAF: _READ_CORE_NAMES,
    _DISPATCH_LEAF: _DISPATCH_NAMES,
    _READ_MODE_LEAF: (*_LEAF_READ_MODE_HELPERS, *_LEAF_FAN_OUT_NAMES),
    _READ_PLAN_LEAF: _READ_PLAN_NAMES,
    _ROLLUPS_LEAF: _ROLLUP_READ_NAMES,
    _BREAKDOWNS_LEAF: (*_BREAKDOWN_READ_NAMES, _SKILL_TRIGGER_RATES_NAME),
    _SKILLS_LEAF: _SKILL_LEAF_NAMES,
    _TABLE_LEAF: _TABLE_NAMES,
    _ISSUE_TABLE_LEAF: _LEAF_ISSUE_TABLE_NAMES,
    _SKILL_TRIGGER_TABLE_LEAF: _LEAF_SKILL_TRIGGER_NAMES,
    _ADOPTION_COLUMNS_LEAF: (*_ADOPTION_VOCABULARY_NAMES, *_ADOPTION_PARAM_NAMES),
    _ADOPTION_SORT_LEAF: _ADOPTION_SORT_NAMES,
    _ADOPTION_HEADERS_LEAF: (_ADOPTION_HEADER_STATE_NAME, *_ADOPTION_HEADER_NAMES),
    _ADOPTION_ROWS_LEAF: (_ADOPTION_ROW_VIEW_NAME, *_ADOPTION_ROW_NAMES),
    _ADOPTION_RENDER_LEAF: (_ADOPTION_CSS_NAME, *_ADOPTION_PANEL_NAMES),
    _SKILL_ADOPTION_HUB: _HUB_SKILL_ADOPTION_NAMES,
    _MATRIX_COLUMNS_LEAF: (*_MATRIX_VOCABULARY_NAMES, *_MATRIX_PARAM_NAMES),
    _MATRIX_SORT_LEAF: _MATRIX_SORT_NAMES,
    _MATRIX_HEADERS_LEAF: (_MATRIX_HEADER_STATE_NAME, *_MATRIX_HEADER_NAMES),
    _MATRIX_ROWS_LEAF: (_MATRIX_ROW_VIEW_NAME, *_MATRIX_ROW_NAMES),
    _MATRIX_RENDER_LEAF: (_MATRIX_CSS_NAME, *_MATRIX_PANEL_NAMES),
    _SKILL_MATRIX_HUB: _HUB_SKILL_MATRIX_NAMES,
    _KPI_SITE: (*_FORWARDED_KPIS, *_FORWARDED_INSIGHTS),
    _KPI_SERIES_LEAF: _FORWARDED_KPI_SERIES,
    _KPI_VALUES_LEAF: (*_KPI_ENTRY_KEYS, *_FORWARDED_KPI_TILES),
    _KPI_STRIP_HUB: (*_FORWARDED_KPI_SERIES, *_FORWARDED_KPI_TILES),
    _READS_HUB: _FORWARDED_READS_HUB,
    _CARD_HEADERS_LEAF: _CARD_MARKUP_NAMES,
    _SPARKLINE_DATA_LEAF: (*_SPARKLINE_POINT_NAMES, _SPARKLINE_PATHS_NAME),
    _SPARKLINE_HTML_LEAF: _LEAF_SPARKLINE_NAMES,
    _SUMMARY_HTML_LEAF: _LEAF_SUMMARY_NAMES,
    _HTML_SURFACE: (
        *_TABLE_NAMES,
        *_HTML_ISSUE_TABLE_NAMES,
        *_HTML_SKILL_TRIGGER_NAMES,
        *_SPARKLINE_POINT_NAMES,
        *_SPARKLINE_MARKUP_NAMES,
        *_SUMMARY_MARKUP_NAMES,
        _SPARKLINE_PATHS_NAME,
    ),
    _BACKEND_CARD_LEAF: _BACKEND_CARD_NAMES,
    _COVERAGE_CARD_LEAF: _COVERAGE_CARD_NAMES,
    _CARD_HUB: _HUB_CARD_NAMES,
    _DRILLDOWN_LEAF: _DRILLDOWN_CALL_NAMES,
    _WIDGET_MODELS_LEAF: _PAGE_STATE_NAMES,
    _WIDGET_RUNS_LEAF: _RUN_SECTION_NAMES,
    _WIDGET_SKILLS_LEAF: _SKILL_PANEL_NAMES,
    _WIDGET_STATES_LEAF: _PAGE_END_NAMES,
    _WIDGET_USAGE_LEAF: _USAGE_PANEL_NAMES,
    _WIDGET_COSTS_LEAF: (
        *_COST_PANEL_NAMES,
        *_RELIABILITY_PANEL_NAMES,
        *_ACTIVITY_PANEL_NAMES,
    ),
})

# The one site that forwards and still answers for something of its own: the
# widget hub publishes the page state, the four sections beneath the hero card,
# the per-issue trace, the two states the page leaves through with the line it
# ends on, and the Plotly defaults while still claiming the render
# passes it stamps, so it is held to resolving what it forwards rather than to
# defining nothing.
_PARTLY_FORWARDED_MODULES = MappingProxyType({
    _WIDGET_HUB: _WIDGET_HUB_NAMES,
})

# The hub the page and the compatibility facade in front of it read the state
# off. It keeps the two historical aliases for the inline presets and the four
# private spellings a caller reached it for, so those are pinned beside the
# public names.
_FORWARDED_HUB = (
    *_PRESET_NAMES,
    *_OFFSET_NAMES,
    *_READ_MODE_NAMES,
    *_HUB_READ_MODE_HELPERS,
    *_WINDOW_NAMES,
    *_FILTER_NAMES,
    _HUB_TRUTHY_NAME,
    _HUB_EXTENT_NAME,
    _HUB_FAN_OUT_NAME,
    ("PRESET_3D", _WINDOWS, "PRESET_RECENT_THREE_DAYS"),
    ("PRESET_7D", _WINDOWS, "PRESET_RECENT_WEEK"),
)


def _facade_surface() -> frozenset[str]:
    """Public names an importer of the historical site can read off it."""
    facade = import_module(_THEME_FACADE)
    return frozenset(
        name
        for name in facade.__dict__
        if not name.startswith("_") and name != _FUTURE_DIRECTIVE
    )


class ForwardedThemeTest(unittest.TestCase):
    """The historical import site binds the owners' objects, not copies."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        facade = import_module(_THEME_FACADE)
        for owner_name, forwarded in _FORWARDED.items():
            owner = import_module(owner_name)
            for name in forwarded:
                with self.subTest(owner=owner_name, name=name):
                    self.assertIs(getattr(facade, name), getattr(owner, name))

    def test_the_declared_names_are_the_whole_surface(self) -> None:
        # A name the owners grew but the flat module never published would
        # leave a page importing it from two places, and a name published here
        # with no owner behind it is an implementation that came back.
        declared = frozenset(
            name for forwarded in _FORWARDED.values() for name in forwarded
        )
        self.assertEqual(_facade_surface(), declared)

    def test_it_defines_nothing_of_its_own(self) -> None:
        # What keeps the forwarding thin: an implementation here would be a
        # second set of tokens the check above cannot see, because it only
        # compares the names the module was asked for.
        facade = import_module(_THEME_FACADE)
        defined = tuple(
            name
            for name, member in facade.__dict__.items()
            if getattr(member, "__module__", None) == _THEME_FACADE
        )
        self.assertEqual(defined, ())


class ForwardedFlatModuleTest(unittest.TestCase):
    """Every name a defines-nothing flat module publishes is the owner's."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        for module_name, forwarded in _FORWARDED_MODULES.items():
            for name, owner_name, attribute in forwarded:
                with self.subTest(module=module_name, name=name):
                    self.assertIs(
                        getattr(import_module(module_name), name),
                        getattr(import_module(owner_name), attribute),
                    )

    def test_no_flat_module_defines_one_itself(self) -> None:
        # The same rule the theme site is held to, applied to the read, state,
        # KPI-strip, card, HTML, skill-adoption, and skill-matrix hubs, the
        # leaves beneath them including the card-markup one, the two sparkline
        # ones, the chrome one beside them, the two the filter bar is reached
        # through, the
        # shared-table, issue-table, skill-trigger, five adoption, and five
        # matrix ones, the six widget leaves the skill cards, the hero one,
        # and the four sections under it are drawn through, the run listing and
        # the trace beneath it are reached through, the two states the page
        # leaves through and the line it ends on are drawn through, and the
        # page state is
        # threaded through, the site the drill-down's historical call shape is
        # exported from, and the KPI
        # site beside those: a module that defined a name of its own would be a
        # second implementation the check above cannot see, because it only
        # compares the names the module was asked for. The card hub is held to
        # it like the rest -- the
        # `__module__` stamp a claim is made with mutates the function, so
        # claiming a name there would move an owner's own object off the owner
        # that defines it.
        for module_name in _FORWARDED_MODULES:
            defined = tuple(
                name
                for name, member in import_module(module_name).__dict__.items()
                if getattr(member, "__module__", None) == module_name
            )
            with self.subTest(module=module_name):
                self.assertEqual(defined, ())


class PartlyForwardedSiteTest(unittest.TestCase):
    """A site that kept members of its own forwards the moved ones."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        for module_name, forwarded in _PARTLY_FORWARDED_MODULES.items():
            for name, owner_name, attribute in forwarded:
                with self.subTest(module=module_name, name=name):
                    self.assertIs(
                        getattr(import_module(module_name), name),
                        getattr(import_module(owner_name), attribute),
                    )


class ForwardedStateHubTest(unittest.TestCase):
    """The hub the page reads binds the owners' objects, not copies."""

    def test_each_name_resolves_to_the_owner(self) -> None:
        hub = import_module(_STATE_HUB)
        for name, owner_name, attribute in _FORWARDED_HUB:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(hub, name),
                    getattr(import_module(owner_name), attribute),
                )


if __name__ == "__main__":
    unittest.main()
