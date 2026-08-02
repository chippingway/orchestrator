# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the usage chart's daily rollups.

The four bands a day is counted into, the mode the stack is switched with, the
roll-up of the series into per-day buckets, the completion of the days only
the per-backend read saw, and the height each stack reaches are the charts
owners' own objects. The trace, axis, and figure leaves that name this module
reach those rather than a copy, so a band cannot be accumulated under one
spelling here and read under another beneath the owner.
"""
from __future__ import annotations

from orchestrator.observability.dashboard.charts import usage_bands
from orchestrator.observability.dashboard.charts import usage_series


BACKEND_MODE = usage_bands.BACKEND_MODE
CACHE_BAND = usage_bands.CACHE_BAND
COST_BAND = usage_bands.COST_BAND
INPUT_BAND = usage_bands.INPUT_BAND
OUTPUT_BAND = usage_bands.OUTPUT_BAND
_backend_names = usage_series.backend_names
_daily_token_total = usage_bands.daily_token_total
_date_axis = usage_series.date_axis
_empty_token_bucket = usage_bands.empty_token_bucket
_ensure_backend_days = usage_series.ensure_backend_days
_roll_up_time_series = usage_bands.roll_up_time_series
_usage_stack_totals = usage_series.usage_stack_totals
