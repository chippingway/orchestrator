# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One resume, the single retry behind it, and what each attempt may persist.

A resume is not one agent run: a session whose transcript was garbage-collected
or outgrew the context window fails deterministically, and the only recovery is
to drop the pinned id and spawn fresh in the same worktree. That retry happens
here rather than a tick later so a Claude session GC'd between polls does not
park the issue for two ticks before recovering.

The order the attempts and the writes are in is the contract. The pause check
runs after BOTH runs, because each opens its own live-pause window -- the first
before the retry spawns a second agent, the second before anything is persisted
-- and a fired guard returns before the session id is pinned and before
`awaiting_human` is cleared, so the next tick re-derives the resume from
untouched durable state. The stage the run is attributed to is resolved once, at
build time, and an explicit `stage` wins over the label read off the issue: a
caller that just relabeled (validating -> fixing) holds an `Issue` whose cached
labels PyGithub did not refresh, so the read would charge the developer's run to
the reviewer's stage.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import guards as _guards, usage as _usage
from orchestrator.workflow.stages.implementing import (
    models as _models,
    session as _session,
    state as _state,
    worktree as _worktree,
)

log = logging.getLogger("orchestrator.workflow")


@dataclass(frozen=True)
class _DevResumeContext:
    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    followup_text: str
    options: _models._DevResumeOptions
    worktree: Path
    plan: _models._DevResumePlan
    stage: str

    @classmethod
    def build(
        cls, request: _models._DevResumeRequest,
    ) -> _DevResumeContext:
        if len(request.resume_args) != 2:
            raise TypeError("expected state and followup_text")
        state, followup_text = request.resume_args
        options = _models._DevResumeOptions.from_fields(request.option_fields)
        worktree = _worktree._ensure_resume_worktree(request.spec, request.issue, state)
        plan = _session._resolve_dev_session_for_resume(request.issue, state)
        # An explicit `stage` wins over the label read off `issue`: a caller
        # that just relabeled the issue (validating -> fixing on
        # CHANGES_REQUESTED) holds an `Issue` whose cached `labels` PyGithub
        # did not refresh after `set_labels`, so `gh.workflow_label(issue)`
        # would still report the pre-flip stage and misattribute the run.
        return cls(
            gh=request.gh,
            spec=request.spec,
            issue=request.issue,
            state=state,
            followup_text=followup_text,
            options=options,
            worktree=worktree,
            plan=plan,
            stage=(
                request.stage
                or request.gh.workflow_label(request.issue)
                or _state._IMPLEMENTING_STAGE
            ),
        )

    def execute(self) -> Tuple[Path, AgentResult, bool]:
        agent_result, paused = self._run_attempt(
            fresh=self.plan.fresh_spawn,
            session_id=self.plan.session.session_id,
        )
        if paused:
            return self.worktree, agent_result, True
        fresh_spawn = self.plan.fresh_spawn
        if self._needs_fresh_retry(agent_result):
            log.info(
                "issue=#%d dropping poisoned dev session %r after poisoned-session "
                "marker (stale or context overflow); retrying once as a fresh spawn",
                self.issue.number, self.plan.session.session_id,
            )
            _session._drop_poisoned_dev_session(self.state)
            fresh_spawn = True
            agent_result, paused = self._run_attempt(
                fresh=True, session_id=None,
            )
            if paused:
                return self.worktree, agent_result, True
        _session._persist_dev_session_after_run(
            self.state,
            agent_result,
            fresh_spawn=fresh_spawn,
            resume_count=self.plan.resume_count,
        )
        return self.worktree, agent_result, False

    def _run_attempt(
        self, *, fresh: bool, session_id: Optional[str],
    ) -> tuple[AgentResult, bool]:
        session = self.plan.session
        agent_result = _usage._run_agent_tracked(
            self.gh,
            self.issue.number,
            agent_role="developer",
            stage=self.stage,
            backend=session.backend,
            prompt=_session._build_dev_spawn_prompt(
                self.spec,
                self.issue,
                self.followup_text,
                followup_has_tracked_repos=(
                    self.options.followup_has_tracked_repos
                ),
                fresh=fresh,
            ),
            cwd=self.worktree,
            agent_spec=session.spec,
            resume_session_id=session_id,
            extra_args=session.extra_args,
            review_round=self.state.get("review_round", 0),
            retry_count=self.state.get(_state._RETRY_COUNT),
        )
        _usage._accumulate_issue_usage(self.state, agent_result.usage)
        paused = (
            self.options.pause_guard
            and _guards._paused_during_agent_run(self.gh, self.issue)
        )
        return agent_result, paused

    def _needs_fresh_retry(self, agent_result: AgentResult) -> bool:
        return (
            self.plan.session.session_id is not None
            and not self.plan.fresh_spawn
            and _session._is_poisoned_session_failure(
                self.plan.session.backend, agent_result,
            )
        )
