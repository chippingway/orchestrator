# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Immutable lazy-export inventory for :mod:`orchestrator.worktrees`."""

from __future__ import annotations

from orchestrator._compat_exports import export_group

EXPORTS = (
    *export_group(
        "logging",
        (("logging", None),),
    ),
    *export_group(
        "orchestrator.git.authentication",
        (
            ("_authed_fetch", "_authed_fetch"),
            ("_authed_target_fetch", "_authed_target_fetch"),
            ("_push_branch", "_push_branch"),
        ),
    ),
    *export_group(
        "orchestrator.git.base_sync.conflicts",
        (
            ("_route_pr_worktree_to_resolving_conflict", "_route_pr_worktree_to_resolving_conflict"),
        ),
    ),
    *export_group(
        "orchestrator.git.base_sync.persistence",
        (("_park_auto_rebase_failure", "_park_auto_rebase_failure"),),
    ),
    *export_group(
        "orchestrator.git.base_sync.pr",
        (("_sync_pr_worktree_to_base", "_sync_pr_worktree_to_base"),),
    ),
    *export_group(
        "orchestrator.git.base_sync.pre_pr",
        (
            ("_merge_base_into_worktree", "_merge_base_into_worktree"),
            ("_rebase_base_into_worktree", "_rebase_base_into_worktree"),
            ("_rebase_in_progress", "_rebase_in_progress"),
        ),
    ),
    *export_group(
        "orchestrator.git.base_sync.recovery",
        (
            ("_recover_pending_auto_base_rebase", "_recover_pending_auto_base_rebase"),
        ),
    ),
    *export_group(
        "orchestrator.git.base_sync.refresh",
        (
            ("_refresh_base_and_worktrees", "_refresh_base_and_worktrees"),
            ("_sync_worktree_with_base", "_sync_worktree_with_base"),
        ),
    ),
    *export_group(
        "orchestrator.git.base_sync.state",
        (
            ("_AUTO_REBASE_PARK_REASONS", "_AUTO_REBASE_PARK_REASONS"),
            ("_PR_REFRESH_DETOUR_LABELS", "_PR_REFRESH_DETOUR_LABELS"),
        ),
    ),
    *export_group(
        "orchestrator.git.commands",
        (
            ("_GIT_NO_PROMPT_ENV", "_GIT_NO_PROMPT_ENV"),
            ("_git", "_git"),
            ("_git_hardened", "_git_hardened"),
        ),
    ),
    *export_group(
        "orchestrator.git.locks",
        (
            ("_TARGET_ROOT_LOCKS", "_TARGET_ROOT_LOCKS"),
            ("_TARGET_ROOT_LOCKS_LOCK", "_TARGET_ROOT_LOCKS_LOCK"),
            ("_target_root_lock", "_target_root_lock"),
        ),
    ),
    *export_group(
        "orchestrator.git.publication.probes",
        (
            ("_CONVENTIONAL_RE", "_CONVENTIONAL_RE"),
            ("_branch_ahead_behind", "_branch_ahead_behind"),
            ("_first_commit_subject", "_first_commit_subject"),
            ("_is_conventional_subject", "_is_conventional_subject"),
            ("_is_prefixed_subject", "_is_prefixed_subject"),
            ("_recent_base_subjects", "_recent_base_subjects"),
        ),
    ),
    *export_group(
        "orchestrator.git.publication.squash",
        (("_squash_and_force_push", "_squash_and_force_push"),),
    ),
    *export_group(
        "orchestrator.git.publication.titles",
        (
            ("_infer_subject_prefix", "_infer_subject_prefix"),
            ("_pr_title_from_commit_or_issue", "_pr_title_from_commit_or_issue"),
        ),
    ),
    *export_group(
        "orchestrator.git.verification.models",
        (("VerifyResult", "VerifyResult"),),
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
        "orchestrator.git.verification.runner",
        (("_run_verify_commands", "_run_verify_commands"),),
    ),
    *export_group(
        "orchestrator.git.worktrees.creation",
        (
            ("_ensure_pr_worktree", "_ensure_pr_worktree"),
            ("_ensure_worktree", "_ensure_worktree"),
            ("_has_new_commits", "_has_new_commits"),
        ),
    ),
    *export_group(
        "orchestrator.git.worktrees.decomposition",
        (
            ("_cleanup_decompose_worktree", "_cleanup_decompose_worktree"),
            ("_decompose_worktree_path", "_decompose_worktree_path"),
            ("_ensure_decompose_worktree", "_ensure_decompose_worktree"),
        ),
    ),
    *export_group(
        "orchestrator.git.worktrees.paths",
        (
            ("_SLUG_SAFE_RE", "_SLUG_SAFE_RE"),
            ("_branch_name", "_branch_name"),
            ("_repo_worktrees_root", "_repo_worktrees_root"),
            ("_resolve_branch_name", "_resolve_branch_name"),
            ("_sanitize_branch_segment", "_sanitize_branch_segment"),
            ("_sanitize_slug", "_sanitize_slug"),
            ("_worktree_path", "_worktree_path"),
        ),
    ),
    *export_group(
        "orchestrator.git.worktrees.recovery",
        (("_branch_has_unpushed_commits", "_branch_has_unpushed_commits"),),
    ),
    *export_group(
        "orchestrator.git.worktrees.terminal",
        (
            ("_cleanup_question_worktree", "_cleanup_question_worktree"),
            ("_cleanup_terminal_branch", "_cleanup_terminal_branch"),
        ),
    ),
)
EXPORTED_NAMES = (
    "VerifyResult",
    "_AUTO_REBASE_PARK_REASONS",
    "_CONVENTIONAL_RE",
    "_GIT_NO_PROMPT_ENV",
    "_PR_REFRESH_DETOUR_LABELS",
    "_SLUG_SAFE_RE",
    "_TARGET_ROOT_LOCKS",
    "_TARGET_ROOT_LOCKS_LOCK",
    "_authed_fetch",
    "_authed_target_fetch",
    "_branch_ahead_behind",
    "_branch_has_unpushed_commits",
    "_branch_name",
    "_cleanup_decompose_worktree",
    "_cleanup_question_worktree",
    "_cleanup_terminal_branch",
    "_decompose_worktree_path",
    "_ensure_decompose_worktree",
    "_ensure_pr_worktree",
    "_ensure_worktree",
    "_first_commit_subject",
    "_git",
    "_git_hardened",
    "_has_new_commits",
    "_head_sha",
    "_infer_subject_prefix",
    "_is_conventional_subject",
    "_is_prefixed_subject",
    "_merge_base_into_worktree",
    "_park_auto_rebase_failure",
    "_pr_title_from_commit_or_issue",
    "_push_branch",
    "_rebase_base_into_worktree",
    "_rebase_in_progress",
    "_recent_base_subjects",
    "_recover_pending_auto_base_rebase",
    "_refresh_base_and_worktrees",
    "_repo_worktrees_root",
    "_resolve_branch_name",
    "_route_pr_worktree_to_resolving_conflict",
    "_run_verify_commands",
    "_sanitize_branch_segment",
    "_sanitize_slug",
    "_squash_and_force_push",
    "_sync_pr_worktree_to_base",
    "_sync_worktree_with_base",
    "_target_root_lock",
    "_truncate_verify_output",
    "_worktree_dirty_files",
    "_worktree_path",
)
