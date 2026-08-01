# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the run matching, answered by its owner.

The five functions are the owner's own, so the request a caller may not spell
twice, the narrowing it goes through, and the order a run's predicates are
asked in are decided once rather than per import site.
"""

from __future__ import annotations

from orchestrator.observability.trajectory_viewer import filtering


resolve_run_filter_options = filtering.resolve_run_filter_options
normalize_run_filters = filtering.normalize_run_filters
matches_scalar_filters = filtering.matches_scalar_filters
matches_dimension_filters = filtering.matches_dimension_filters
matches_run_filters = filtering.matches_run_filters
