# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The frozen records one documenting tick hands between its owners.

`_DocumentingContext` exists so the drift-unwind, worktree-prep, run, and
disposition owners thread one value instead of up to six positional arguments.
`branch` and `pr_number` are tick-invariant once the missing-`pr_number` guard
has passed, so every consumer downstream of it reads them off the context
rather than re-deriving a branch name the pinned state may already override.

`_DocumentingRun` carries what the disposition cannot re-derive after the fact:
`before_sha` is the only thing that tells a commit this run produced from one
already on the branch, `recovered` distinguishes the shortcut that spawned no
agent, and `ahead` is what makes a `DOCS: NO_CHANGE` verdict over a recovered
commit still push it instead of advancing with the docs stranded locally.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState


@dataclass(frozen=True)
class _DocumentingContext:
    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    branch: str
    pr_number: Any


@dataclass(frozen=True)
class _DocumentingRun:
    worktree: Any
    agent_result: AgentResult
    before_sha: str
    recovered: bool
    paused: bool
    ahead: int
