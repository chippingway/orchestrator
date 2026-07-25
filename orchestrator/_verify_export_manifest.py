# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Immutable lazy-export inventory for :mod:`orchestrator.verify`."""

from __future__ import annotations

from orchestrator._compat_exports import export_group

EXPORTS = (
    *export_group(
        "orchestrator.git.verification.models",
        (
            ("VerifyResult", "VerifyResult"),
            ("_VERIFY_OUTPUT_BUDGET", "_VERIFY_OUTPUT_BUDGET"),
        ),
    ),
    *export_group(
        "orchestrator.git.verification.output",
        (("_truncate_verify_output", "_truncate_verify_output"),),
    ),
    *export_group(
        "orchestrator.git.verification.probes",
        (
            ("_head_sha", "_head_sha"),
            ("_worktree_dirty_files", "_worktree_dirty_files"),
        ),
    ),
    *export_group(
        "orchestrator.git.verification.process",
        (
            ("_combine_output", "_combine_output"),
            ("_completed_verify_result", "_completed_verify_result"),
            ("_drain_verify_output", "_drain_verify_output"),
            ("_kill_verify_group", "_kill_verify_group"),
            ("_spawn_verify_command", "_spawn_verify_command"),
            ("_timeout_verify_result", "_timeout_verify_result"),
        ),
    ),
    *export_group(
        "orchestrator.git.verification.runner",
        (
            ("_run_verify_command", "_run_verify_command"),
            ("_run_verify_commands", "_run_verify_commands"),
        ),
    ),
)
EXPORTED_NAMES = None
