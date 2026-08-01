# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical constants import site, answered by the dashboard owners.

The eighteen names are read off the owners that decide them -- the preset
vocabulary from the window owner, the offset range from the filter owner, and
the read-mode knob and refusal message from theirs -- so a caller that names
this module and a caller that names an owner compare against the same objects.
`TRUTHY` keeps the bare spelling published here, which is the one the
parallel-reads flag is parsed against.
"""

from __future__ import annotations

from orchestrator.observability.dashboard import filters, read_mode, windows


DEFAULT_WINDOW_DAYS = windows.DEFAULT_WINDOW_DAYS
PRESET_RECENT_THREE_DAYS = windows.PRESET_RECENT_THREE_DAYS
PRESET_RECENT_WEEK = windows.PRESET_RECENT_WEEK
PRESET_ALL = windows.PRESET_ALL
PRESET_CUSTOM = windows.PRESET_CUSTOM
PRESET_OPTIONS = windows.PRESET_OPTIONS
PRESET_LABELS = windows.PRESET_LABELS
PRESET_INLINE_LABELS = windows.PRESET_INLINE_LABELS
PRESET_DAYS = windows.PRESET_DAYS
DEFAULT_PRESET = windows.DEFAULT_PRESET
MIN_UTC_OFFSET = filters.MIN_UTC_OFFSET
MAX_UTC_OFFSET = filters.MAX_UTC_OFFSET
TZ_OFFSET_OPTIONS = filters.TZ_OFFSET_OPTIONS
DEFAULT_TZ_OFFSET_HOURS = filters.DEFAULT_TZ_OFFSET_HOURS
PARALLEL_READS_ENV = read_mode.PARALLEL_READS_ENV
PARALLEL_READS_MAX_WORKERS = read_mode.PARALLEL_READS_MAX_WORKERS
TRUTHY = read_mode.TRUTHY
UNCONFIGURED_DB_MESSAGE = read_mode.UNCONFIGURED_DB_MESSAGE
