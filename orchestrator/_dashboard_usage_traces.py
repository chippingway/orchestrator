# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the usage chart's traces.

The shaping that decides whether a window has a chart at all, the band a stack
is added one of at a time, the two modes it is stacked in, and the cost line
overlaid on it are the charts owner's own objects. The figure leaf that names
this module reaches those rather than a copy, so the trace an operator reads is
the one the owner drew.
"""
from __future__ import annotations

from orchestrator.observability.dashboard.charts import usage_traces


_COLOR_KEY = usage_traces._COLOR_KEY
_add_backend_usage_traces = usage_traces.add_backend_usage_traces
_add_token_stack_trace = usage_traces.add_token_stack_trace
_add_token_type_usage_traces = usage_traces.add_token_type_usage_traces
_add_usage_cost_trace = usage_traces.add_usage_cost_trace
_add_usage_stack_traces = usage_traces.add_usage_stack_traces
_prepare_usage_data = usage_traces.prepare_usage_data
