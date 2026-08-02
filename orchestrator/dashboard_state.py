# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Stable dashboard state surface backed by the observability owners."""
from __future__ import annotations

import sys

from orchestrator.observability.dashboard import fanout, filters, windows
from orchestrator.observability.dashboard import read_mode as read_constants


DEFAULT_WINDOW_DAYS = windows.DEFAULT_WINDOW_DAYS
PRESET_RECENT_THREE_DAYS = windows.PRESET_RECENT_THREE_DAYS
PRESET_RECENT_WEEK = windows.PRESET_RECENT_WEEK
setattr(sys.modules[__name__], "PRESET_3D", PRESET_RECENT_THREE_DAYS)
setattr(sys.modules[__name__], "PRESET_7D", PRESET_RECENT_WEEK)
PRESET_ALL = windows.PRESET_ALL
PRESET_CUSTOM = windows.PRESET_CUSTOM
PRESET_OPTIONS = windows.PRESET_OPTIONS
PRESET_LABELS = windows.PRESET_LABELS
PRESET_INLINE_LABELS = windows.PRESET_INLINE_LABELS
PRESET_DAYS = windows.PRESET_DAYS
DEFAULT_PRESET = windows.DEFAULT_PRESET
TZ_OFFSET_OPTIONS = filters.TZ_OFFSET_OPTIONS
DEFAULT_TZ_OFFSET_HOURS = filters.DEFAULT_TZ_OFFSET_HOURS
PARALLEL_READS_ENV = read_constants.PARALLEL_READS_ENV
PARALLEL_READS_MAX_WORKERS = read_constants.PARALLEL_READS_MAX_WORKERS
_TRUTHY = read_constants.TRUTHY
UNCONFIGURED_DB_MESSAGE = read_constants.UNCONFIGURED_DB_MESSAGE
_parse_parallel_reads_flag = read_constants.parse_parallel_reads_flag
DASHBOARD_PARALLEL_READS = read_constants.DASHBOARD_PARALLEL_READS
DateWindow = windows.DateWindow
default_date_range = windows.default_date_range
to_window = windows.to_window
_extent_dates = windows.extent_dates
preset_window = windows.preset_window
previous_window = windows.previous_window
format_tz_offset = filters.format_tz_offset
shift_ts = filters.shift_ts
parse_issue_number = filters.parse_issue_number
resolve_stage_filter = filters.resolve_stage_filter
DashboardCacheKey = filters.DashboardCacheKey
cache_key = filters.cache_key
db_unconfigured_message = read_constants.db_unconfigured_message
dashboard_parallel_reads_enabled = read_constants.dashboard_parallel_reads_enabled
_fan_out_reads = fanout.fan_out_reads
