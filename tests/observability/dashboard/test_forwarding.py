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

_TABLE_LEAF = "orchestrator._dashboard_table_html"

# `from __future__ import annotations` opens every module in the repository and
# binds the compiler directive under a public name. It is a compilation
# instruction rather than something the theme answers for, so the surface check
# looks past it.
_FUTURE_DIRECTIVE = "annotations"

_PACKAGE = "orchestrator.observability.dashboard"

_BACKEND_CARD = f"{_PACKAGE}.backend_card"

_BREAKDOWNS = f"{_PACKAGE}.breakdowns"

_CARD_HTML = f"{_PACKAGE}.card_html"

_COVERAGE_CARD = f"{_PACKAGE}.coverage_card"

_CSS = f"{_PACKAGE}.css"

_DISPATCH = f"{_PACKAGE}.dispatch"

_FANOUT = f"{_PACKAGE}.fanout"

_FILTER_BINDING = f"{_PACKAGE}.filter_binding"

_FILTERS = f"{_PACKAGE}.filters"

_FORMATTING = f"{_PACKAGE}.formatting"

_INSIGHTS = f"{_PACKAGE}.insights"

_ISSUE_TABLE = f"{_PACKAGE}.issue_table"

_KPIS = f"{_PACKAGE}.kpis"

_KPI_SERIES = f"{_PACKAGE}.kpi_series"

_KPI_STRIP = f"{_PACKAGE}.kpi_strip"

_LAYOUT = f"{_PACKAGE}.layout"

_PALETTE = f"{_PACKAGE}.palette"

_READ_MODE = f"{_PACKAGE}.read_mode"

_READ_PLAN = f"{_PACKAGE}.read_plan"

_ROLLUPS = f"{_PACKAGE}.rollups"

_SCOPED_READS = f"{_PACKAGE}.scoped_reads"

_SKILLS = f"{_PACKAGE}.skills"

_STATIC_METADATA = f"{_PACKAGE}.static_metadata"

_TABLES = f"{_PACKAGE}.tables"

_TOKENS = f"{_PACKAGE}.tokens"

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
# stylesheet paints, a table drawn here the one every hand-rolled panel is, and
# a window's issues ranked here the ones the page lists,
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
    _READ_CORE_LEAF: _READ_CORE_NAMES,
    _DISPATCH_LEAF: _DISPATCH_NAMES,
    _READ_MODE_LEAF: (*_LEAF_READ_MODE_HELPERS, *_LEAF_FAN_OUT_NAMES),
    _READ_PLAN_LEAF: _READ_PLAN_NAMES,
    _ROLLUPS_LEAF: _ROLLUP_READ_NAMES,
    _BREAKDOWNS_LEAF: (*_BREAKDOWN_READ_NAMES, _SKILL_TRIGGER_RATES_NAME),
    _SKILLS_LEAF: _SKILL_LEAF_NAMES,
    _TABLE_LEAF: _TABLE_NAMES,
    _ISSUE_TABLE_LEAF: _LEAF_ISSUE_TABLE_NAMES,
    _KPI_SITE: (*_FORWARDED_KPIS, *_FORWARDED_INSIGHTS),
    _KPI_SERIES_LEAF: _FORWARDED_KPI_SERIES,
    _KPI_VALUES_LEAF: (*_KPI_ENTRY_KEYS, *_FORWARDED_KPI_TILES),
    _KPI_STRIP_HUB: (*_FORWARDED_KPI_SERIES, *_FORWARDED_KPI_TILES),
    _READS_HUB: _FORWARDED_READS_HUB,
    _CARD_HEADERS_LEAF: _CARD_MARKUP_NAMES,
    _HTML_SURFACE: (*_TABLE_NAMES, *_HTML_ISSUE_TABLE_NAMES),
    _BACKEND_CARD_LEAF: _BACKEND_CARD_NAMES,
    _COVERAGE_CARD_LEAF: _COVERAGE_CARD_NAMES,
    _CARD_HUB: _HUB_CARD_NAMES,
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
        # KPI-strip, card, and HTML hubs, the leaves beneath them including the
        # card-markup and the shared-table and issue-table ones, and the KPI
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
