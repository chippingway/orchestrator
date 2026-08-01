# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the file-backed read model, answered by its owners.

Every name here is the object an owner defines, so a caller that has always
reached the reader through this module keeps holding what the page renders,
what a filter narrows, and what the KPI strip is totalled from. The record half
comes off the record facade -- and off a *freshly loaded* one, because that
facade captures the analytics package it resolves the log path through at its
own import, so rebuilding this module against a patched environment has to
rebuild that capture with it. The filter and summary halves need no such world:
they are pure over the runs they are handed, so they are bound straight off
their owners.

Three of those shapes report this module rather than the owner that defines
them, so this is where their annotations are read back from: ``get_type_hints``
resolves a class's annotations in the globals of the module it names, and under
``from __future__ import annotations`` those annotations are text. That is why
the typing vocabulary they are spelled in is imported here for nothing else.
"""

from __future__ import annotations

from typing import Optional as Optional, Sequence as Sequence

from orchestrator import _trajectory_reader_bootstrap as bootstrap
from orchestrator.observability.trajectory_viewer import (
    filter_models,
    filter_values,
    filtering,
    summaries,
)


records = bootstrap.load_fresh_records()
TIMELINE_OUTPUT = records.TIMELINE_OUTPUT
TIMELINE_PROMPT = records.TIMELINE_PROMPT
TRAJECTORY_EVENT = records.TRAJECTORY_EVENT
TimelineEntry = records.TimelineEntry
TrajectoryRun = records.TrajectoryRun
TrajectoryStepView = records.TrajectoryStepView
RunUsageView = records.RunUsageView
TurnUsageView = records.TurnUsageView
UNCONFIGURED_LOG_MESSAGE = records.UNCONFIGURED_LOG_MESSAGE
log_unconfigured_message = records.log_unconfigured_message
parse_record = records.parse_record
read_trajectories = records.read_trajectories
resolve_log_path = records.resolve_log_path
FilterOptions = filter_models.FilterOptions
RunFilterOptions = filter_models.RunFilterOptions
TrajectorySummary = summaries.TrajectorySummary
filter_options = filter_values.filter_options
filter_runs = filtering.filter_runs
summarize = summaries.summarize
