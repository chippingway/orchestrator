# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The records one validating tick hands between its owners.

Each carries something the owner downstream cannot re-derive. `_ReviewerRun`
holds the worktree the reviewer actually ran in and the round it ran as, so
the approval gate verifies the same checkout that was reviewed and the
feedback comment names the round the human sees on the PR. `_ReviewerDecision`
folds the parsed verdict together with the run, and its `feedback` falls back
to the agent's last message so a reviewer that put its reasoning above the
VERDICT line still reaches the dev. `_DevFixRun` carries `before_sha` -- the
pre-agent HEAD is the only thing that tells a commit this run produced from
one already on the branch -- and an optional `after_sha` for the caller that
has already read it.

`_AwaitingValidation` is the awaiting-human context: it snapshots the park
reason and the trusted comments that arrived since the last consumed one, and
its two mutators are the pair every route through that park owes -- clearing
the flags, and ratcheting `last_action_comment_id` past the comments it just
fed to an agent. Reading both once at build time is what keeps the three
decision helpers agreeing on the same batch. The orchestrator's own comments
are dropped from that batch by recorded id AND by the hidden body marker,
because every helper here reads a non-empty batch as "a human replied": a
comment this process posted and then failed to record -- the pinned write that
would have named it never landed -- is still ours, and the marker is what says
so when the id ledger cannot. `_RequestedChanges` and
`_AwaitingDevAttempt` bracket the fix that follows a verdict: the first
freezes what the CHANGES_REQUESTED route needs, the second reports whether
the resume that ran was cut short by a live pause.

`_dev_fix_run` validates rather than carries. Both fix-disposition entry
points still accept the historical positional call, so it binds one of those
calls to a `_DevFixRun` and raises on an unknown keyword rather than
swallowing a mistyped `after_sha=`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.github.client import GitHubClient
from orchestrator.github.comments import filter_trusted
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.stages.validating import state as _state


@dataclass(frozen=True)
class _ReviewerRun:
    wt: Path
    round_n: int
    pr_number: Any
    agent_result: AgentResult


@dataclass(frozen=True)
class _ReviewerDecision:
    run: _ReviewerRun
    verdict: str
    body: str

    @property
    def feedback(self) -> str:
        return (
            self.body.strip()
            or (self.run.agent_result.last_message or "").strip()
        )


@dataclass(frozen=True)
class _DevFixRun:
    worktree: Path
    agent_result: AgentResult
    before_sha: str
    after_sha: Optional[str] = None


@dataclass(frozen=True)
class _RequestedChanges:
    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    decision: _ReviewerDecision


@dataclass(frozen=True)
class _AwaitingValidation:
    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    park_reason: Any
    comments: list

    @classmethod
    def build(
        cls, gh: GitHubClient, spec: config.RepoSpec, issue: Issue, state: PinnedState,
    ) -> _AwaitingValidation:
        # Filtered by recorded id AND by `_ORCH_COMMENT_MARKER`, the same
        # pair `_rescan_fixing_feedback` uses and for the same two reasons:
        # the id ledger is capped and evicts on long-lived issues, and a
        # comment posted by a tick whose pinned write then failed was never
        # recorded at all. Either one left in reads as a human reply.
        orchestrator_ids = _comments._orchestrator_ids(state)
        unread = [
            issue_comment
            for issue_comment in gh.comments_after(
                issue, state.get("last_action_comment_id"),
            )
            if issue_comment.id not in orchestrator_ids
            and _comments._ORCH_COMMENT_MARKER not in (issue_comment.body or "")
        ]
        return cls(
            gh,
            spec,
            issue,
            state,
            state.get(_state._PARK_REASON),
            filter_trusted(unread),
        )

    def clear_park(self) -> None:
        self.state.set("awaiting_human", False)
        self.state.set(_state._PARK_REASON, None)

    def consume_comments(self) -> None:
        self.state.set(
            "last_action_comment_id",
            max(comment.id for comment in self.comments),
        )


@dataclass(frozen=True)
class _AwaitingDevAttempt:
    run: _DevFixRun
    paused: bool


def _dev_fix_run(context_args: tuple, fields: dict) -> tuple[PinnedState, _DevFixRun]:
    if len(context_args) != 4:
        raise TypeError("expected state, worktree, result, and before_sha")
    state, worktree, agent_result, before_sha = context_args
    unknown = set(fields) - {"after_sha"}
    if unknown:
        raise TypeError(f"unexpected fix-result option(s): {sorted(unknown)!r}")
    return state, _DevFixRun(
        worktree, agent_result, before_sha, fields.get("after_sha"),
    )
