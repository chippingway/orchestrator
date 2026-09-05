# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Frozen inputs and decisions threaded through one auto-rebase attempt.

The contexts live together because they are one another's continuations: the
legacy request derives a context, that context is what every publish and park
helper receives, and the recovery context is the same attempt re-read from
pinned state after a crash. Keeping them in one owner is what stops the fields
a resumed attempt carries from drifting away from the fields the interrupted
one recorded.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from github.Issue import Issue

from orchestrator import config
from orchestrator.git.base_sync.state import (
    _PENDING_REWRITE_PR,
    _PENDING_REWRITE_SHA,
    _PENDING_REWRITE_STAGE,
)
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.state import (
    WorkflowLabel,
    publishes_onto_a_pull_request,
)


@dataclass(frozen=True)
class _PendingRewrite:
    """What one interrupted attempt recorded about the replay it made.

    Three facts, written in one statement and read as one, because a caller
    holding any of them apart would be free to fill the others in from the
    world it woke up in. The head is what says the checkout in front of a
    recovery is that attempt's own work. The pull request and the stage are
    what the permit's publication checks are asked AGAINST -- taken from the
    issue as it reads now they would compare today with today, and a relabel
    or a repoint made while the process was down would pass as the dead tick's
    own terms.

    Absent is the window between `git rebase` returning and the write that
    records this, and `is_recorded` is what every caller asks: an attempt that
    reached that write can be reconciled against, and one that did not is
    handled by the readings a recovery can still take for itself.
    """

    sha: str = ""
    pr_number: int = 0
    stage: WorkflowLabel | None = None

    @property
    def is_recorded(self) -> bool:
        """Whether all three facts came back in the shape they claim."""
        return bool(self.sha) and self.pr_number > 0 and self.stage is not None

    def names(self, local_head: str) -> bool:
        """Whether this record vouches for the commit a checkout stands on."""
        return self.is_recorded and bool(local_head) and self.sha == local_head


def _pending_rewrite(state: PinnedState) -> _PendingRewrite:
    """The record one interrupted attempt left of the replay it made.

    Read whole or not at all, like every other record this domain acts on: a
    group short of a member, a pull request that is not an identity, and a
    stage no publication is entered from each answer as no record, which every
    caller reads as "cannot say" rather than as a fact about the world.
    """
    recorded = state.get(_PENDING_REWRITE_SHA)
    number = state.get(_PENDING_REWRITE_PR)
    stage = _recorded_stage(state.get(_PENDING_REWRITE_STAGE))
    if not isinstance(recorded, str) or not isinstance(number, int):
        return _PendingRewrite()
    if isinstance(number, bool) or number <= 0 or stage is None:
        return _PendingRewrite()
    return _PendingRewrite(sha=recorded, pr_number=number, stage=stage)


def _recorded_stage(recorded: object) -> WorkflowLabel | None:
    """The stage a record names, or None where it names no publication.

    Held to the same predicate the permit holds its own evidence to -- the
    states that push onto a pull request the remote already carries -- so a
    record naming any other describes an attempt this workflow never made.
    """
    try:
        stage = WorkflowLabel(recorded)
    except ValueError:
        return None
    return stage if publishes_onto_a_pull_request(stage) else None


@dataclass(frozen=True)
class _AutoRebaseContext:
    """Stable inputs for one refresh-time PR rebase attempt."""

    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    worktree: Path
    pr_number: int
    behind: int
    label: WorkflowLabel | None
    pending_pre_rebase_sha: str | None


@dataclass(frozen=True)
class _AutoRebaseRequest:
    """Legacy refresh arguments before derived synchronization fields."""

    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    worktree: Path
    pr_number: int
    behind: int

    def to_context(self, pending_field: str) -> _AutoRebaseContext:
        """Derive label and recovery state at the compatibility boundary."""
        return _AutoRebaseContext(
            gh=self.gh,
            spec=self.spec,
            issue=self.issue,
            state=self.state,
            worktree=self.worktree,
            pr_number=self.pr_number,
            behind=self.behind,
            label=self.gh.workflow_label(self.issue),
            pending_pre_rebase_sha=self.state.get(pending_field),
        )


@dataclass(frozen=True)
class _AutoRebaseRecoveryContext:
    """Stable inputs for finalizing one interrupted auto-rebase."""

    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    worktree: Path
    pr_number: int
    label: str
    pending_pre_rebase_sha: str
    # What the interrupted attempt recorded about its own replay, where it got
    # as far as recording anything: the head it produced, and the publication
    # it produced it for. The anchor beside it names the lease and can prove
    # neither, so this is what says the checkout in front of this recovery is
    # that attempt's work and what its permit's terms are re-asked against.
    pending_rewrite: _PendingRewrite = _PendingRewrite()
    behind: int = 0
    unparking_consumed_max: int | None = None


@dataclass(frozen=True)
class _AutoRebaseRecoverySnapshot:
    """Local and remote branch state observed during crash recovery."""

    branch: str
    local_head: str
    remote_head: str = ""
    ahead: int = 0
    behind: int = 0


@dataclass(frozen=True)
class _AutoRebaseDecision:
    """Whether the coordinator should continue its normal rebase flow."""

    should_continue: bool
    consumed_comment_id: int | None = None


@dataclass(frozen=True)
class _ConflictRouteContext:
    """Stable inputs for routing an auto-rebase conflict to its handler."""

    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    pr_number: int
    label: str
    behind: int
    conflicted_files: list[str]
    pr_head_sha: str | None
