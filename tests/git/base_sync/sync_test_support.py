# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Git doubles and the collaborator patch table the base-sync tests share."""

from __future__ import annotations

import contextlib
import subprocess
from types import MappingProxyType
from unittest.mock import patch

from orchestrator import base_sync
from orchestrator.git import authentication, commands
from orchestrator.git.base_sync import pre_pr, refresh
from orchestrator.git.publication import probes as publication_probes
from orchestrator.git.verification import probes as verification_probes
from orchestrator.git.worktrees import paths


def _git_result(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# Keyword aliases -> every module attribute the alias has to replace. The
# refresh, pre-PR, eligibility, startup, publication, and crash-recovery owners
# read their collaborators off the owning modules while the remaining base-sync
# leaves still read theirs off the `base_sync` facade, so a name both sides
# call is listed on both sides -- patching one alone would leave half the flow
# talking to real git.
_BASE_SYNC_TARGETS = MappingProxyType(
    {
        "dirty": (
            (base_sync, "_worktree_dirty_files"),
            (verification_probes, "_worktree_dirty_files"),
        ),
        "rebase": (
            (base_sync, "_rebase_base_into_worktree"),
            (pre_pr, "_rebase_base_into_worktree"),
        ),
        "push": (
            (base_sync, "_push_branch"),
            (authentication, "_push_branch"),
        ),
        "head_sha": (
            (base_sync, "_head_sha"),
            (verification_probes, "_head_sha"),
        ),
        "git": ((base_sync, "_git"), (commands, "_git")),
        "hardened": (
            (base_sync, "_git_hardened"),
            (commands, "_git_hardened"),
        ),
        "fetch": (
            (base_sync, "_authed_fetch"),
            (authentication, "_authed_fetch"),
        ),
        "ahead_behind": (
            (base_sync, "_branch_ahead_behind"),
            (publication_probes, "_branch_ahead_behind"),
        ),
        "target_fetch": (
            (base_sync, "_authed_target_fetch"),
            (authentication, "_authed_target_fetch"),
        ),
        "worktrees_root": (
            (base_sync, "_repo_worktrees_root"),
            (paths, "_repo_worktrees_root"),
        ),
        "sync": (
            (base_sync, "_sync_worktree_with_base"),
            (refresh, "_sync_worktree_with_base"),
        ),
    }
)


@contextlib.contextmanager
def _patch_base_sync(**mocks):
    """Patch the base-sync collaborators named by keyword alias for the
    block. Aliases resolve to the modules that read them via
    `_BASE_SYNC_TARGETS`; each value is the object installed in their place.
    Only the named collaborators are patched."""
    with contextlib.ExitStack() as stack:
        for alias, mock in mocks.items():
            for module, attribute in _BASE_SYNC_TARGETS[alias]:
                stack.enter_context(patch.object(module, attribute, mock))
        yield
