# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Static compatibility inventory for ``orchestrator.github``."""
from __future__ import annotations

from orchestrator import _github_checks, _github_internals

GitHubClientBase = _github_internals.GitHubInternalsMixin

CheckSurfaceRead = _github_checks.CheckSurfaceRead
normalize_combined_status = _github_checks.normalize_combined_status
normalize_check_runs = _github_checks.normalize_check_runs
fold_check_states = _github_checks.fold_check_states
failed_check_run_conclusions = _github_checks._FAILED_CHECK_RUN_CONCLUSIONS
successful_check_run_conclusions = (
    _github_checks._SUCCESSFUL_CHECK_RUN_CONCLUSIONS
)
check_state_failure = _github_checks._CHECK_STATE_FAILURE
check_state_pending = _github_checks._CHECK_STATE_PENDING
