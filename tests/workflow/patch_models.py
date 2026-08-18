# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Typed inputs and basic mock builders for workflow test runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import MagicMock

from orchestrator.agents import AgentResult

from tests.workflow.repo_values import BASE_TIP_SHA


@dataclass(frozen=True)
class _AgentResultSeed:
    session_id: str = "sess-1"
    last_message: str = ""
    timed_out: bool = False
    interrupted: bool = False
    stderr: str = ""
    exit_code: Optional[int] = None


@dataclass(frozen=True)
class _WorkflowRunContext:
    run_agent: Any
    has_new_commits: Any = False
    dirty_files: tuple = ()
    tree_readable: bool = True
    committed_paths: tuple = ()
    head_contains_path: bool = True
    push_branch: bool = True
    anchor_pr_head: Any = True
    head_shas: tuple = ("",)
    # Whether the checkout's HEAD is the per-issue branch. True by default,
    # since that is what a round runs on; a test about a commit made detached
    # says otherwise, and the plan publication refuses on it.
    head_on_branch: bool = True
    branch_tip_sha: str = ""
    remote_base_tip: Optional[str] = BASE_TIP_SHA
    remote_branch_tip: Optional[str] = ""
    commit_contains: Any = True
    unpushed_branch: Optional[str] = None
    first_commit_subject: str = ""
    fallback_prefix: Optional[str] = None
    squash_result: tuple = (True, None, 0, None)
    branch_ahead_behind: tuple = (0, 0)
    rebase_in_progress: bool = False
    verify_result: Any = None
    authed_fetch_result: Any = None
    analytics_log_path: Any = None
    trajectory_log_path: Any = None


def _agent(**agent_fields) -> AgentResult:
    seed = _AgentResultSeed(**agent_fields)
    exit_code = seed.exit_code
    if exit_code is None:
        exit_code = -1 if seed.timed_out else 0
    return AgentResult(
        session_id=seed.session_id,
        last_message=seed.last_message,
        exit_code=exit_code,
        timed_out=seed.timed_out,
        stdout="",
        stderr=seed.stderr,
        interrupted=seed.interrupted,
    )


class _AnchorAnswers:
    """What the handoff's move of a branch onto a PR head reports.

    The SHA the branch ended up on, since that is what the baseline the spawn
    path reads back is then measured by. `True` is the ordinary answer -- it
    landed on the head that was asked for -- a string is a test naming a
    different tip (the base, where a plan branch the remote no longer has sends
    it), and `None` is the move that established nothing, which holds the
    handoff.
    """

    def __init__(self, context: _WorkflowRunContext) -> None:
        self._context = context

    def __call__(self, spec, issue_number, *, branch: str, head_sha: str):
        landed = self._context.anchor_pr_head
        if landed is True:
            # No head named is the caller asking for the base outright, which
            # is where a finished pull request's branch ends up.
            return head_sha or BASE_TIP_SHA
        return landed or None


class _RemoteTipAnswers:
    """Answer the remote-tip read by which branch it is asked about.

    One seam, two questions: the base a round pins its diff against, and the
    per-issue branch a publication is about to move. A single value would
    answer both with the same SHA, so no test could seed one without seeding
    the other -- and the publication gate reads the second to decide whether
    the branch is still one it may overwrite.
    """

    def __init__(self, context: _WorkflowRunContext) -> None:
        self._context = context

    def __call__(self, spec, worktree, branch: str):
        if branch == spec.base_branch:
            return self._context.remote_base_tip
        return self._context.remote_branch_tip


def _default_infer_subject_prefix(spec, worktree, issue):
    labels = {
        (getattr(label, "name", "") or "").lower()
        for label in (getattr(issue, "labels", None) or [])
    }
    return "fix" if {"bug", "fix"} & labels else "feat"


def _as_mock(value_or_sequence):
    if callable(value_or_sequence):
        return value_or_sequence
    mock = MagicMock()
    if isinstance(value_or_sequence, (list, tuple)):
        mock.side_effect = list(value_or_sequence)
    else:
        mock.return_value = value_or_sequence
    return mock
