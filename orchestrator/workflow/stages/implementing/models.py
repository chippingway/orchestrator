# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The frozen records one implementing tick hands between its owners.

Each one exists because a value has to survive a boundary the spawn cannot see
across. `_PreparedDevRun` carries `before_sha` -- the pre-agent HEAD -- from
whoever started the run to whoever disposes it, because that watermark is the
only thing that tells a commit produced by THIS run from one already on the
branch. `_AgentWork` and `_PRWork` carry the worktree (and, once pushed, the
branch) so the publication owner never re-derives either. `_DevSession` and
`_DevResumePlan` freeze the locked spec, backend, args, and session id together
with the fresh-spawn decision, so a resume cannot half-rotate a session.

`_DevResumeRequest` and `_DevResumeOptions` are the exception: they validate
rather than carry. The resume entry point still accepts the historical
positional-and-keyword call, so the request freezes what one `inspect`-bound
call supplied and the options reject an unknown keyword that would otherwise be
swallowed silently instead of raising the `TypeError` a mistyped `pause_guard=`
deserves.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.github.client import GitHubClient
from orchestrator.workflow import state as _workflow_state
from orchestrator.workflow.stages.implementing import state as _state


@dataclass(frozen=True)
class _PreparedDevRun:
    agent_result: AgentResult
    before_sha: Optional[str]
    paused: bool
    worktree: Path


@dataclass(frozen=True)
class _AgentWork:
    agent_result: AgentResult
    worktree: Path


@dataclass(frozen=True)
class _PRWork(_AgentWork):
    branch: str


@dataclass(frozen=True)
class _DevSession:
    spec: str
    backend: str
    extra_args: tuple[str, ...]
    session_id: Optional[str]


@dataclass(frozen=True)
class _DevResumePlan:
    session: _DevSession
    fresh_spawn: bool
    resume_count: int


@dataclass(frozen=True)
class _DevResumeRequest:
    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    resume_args: tuple
    option_fields: dict
    stage: Optional[str]

    @property
    def resolved_stage(self) -> str:
        """Name the stage every record this run emits is attributed to.

        An explicit override wins: the caller that passes one relabeled the
        issue and then resumed on the SAME ``Issue`` object, whose cached
        labels PyGithub does not refresh, so the label read would report the
        stage the run just left. Otherwise the label the issue carries names
        it -- by its bare tag, which is what the audit, analytics, and
        trajectory records have always keyed on.
        """
        return (
            self.stage
            or _workflow_state.stage_name(self.gh.workflow_label(self.issue))
            or _state._IMPLEMENTING_STAGE
        )


@dataclass(frozen=True)
class _DevResumeOptions:
    followup_has_tracked_repos: bool = False
    pause_guard: bool = False

    @classmethod
    def from_fields(cls, fields: dict) -> _DevResumeOptions:
        unknown = set(fields) - {"followup_has_tracked_repos", "pause_guard"}
        if unknown:
            raise TypeError(f"unexpected resume option(s): {sorted(unknown)!r}")
        return cls(**fields)
