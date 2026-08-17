# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The records one discussion tick hands between its owners.

`_DiscussionRun` bundles the four handles a tick is driven by so the owners
never re-read pinned state: the session id the spawn retains, the usage the
assessment folds, and the park the routing publishes all have to land on the
one `state` object the handler read at the top, or the single write at the end
drops whichever mutation was made against a second copy.

`_DiscussionSession` is the agent identity one round runs under, carried as the
full configured spec rather than a bare backend so that what is pinned on the
issue and what the command line actually was cannot disagree, and beside it the
conversation that spec is mid-way through. The two travel together because a
resume needs both and neither survives being re-derived: the spec says which
backend the session id is even valid on, so reading one from pinned state and
the other from the current config would hand a live conversation to a CLI that
never opened it. It is a plain carrier because which identity applies is a
property of the issue, not of the class: `run` reads the pinned one back when
there is one, and only an issue that has never spawned falls through to the
current config -- which is also the only issue whose session id is absent
rather than merely unreturned.

`_DiscussionRound` carries the finished run beside the HEAD the checkout was
sitting on when the round opened, because "did this agent commit?" is not a
question the worktree can answer on its own: the issue may have arrived here
from a PR stage with commits already on its branch, and a base-relative probe
would read those as this round's work.

`_DiscussionPrompt` pairs what a round is asked with the replies asking it has
therefore consumed, because the two are one decision made once. A full-context
round reads the thread to build its text and the ceiling it may record from the
same snapshot; splitting them would let a comment land between two reads, reach
the agent through one, and stay above the watermark set by the other -- and a
stage that reads no comment twice would then send it again next tick.

`_DiscussionOutcome` is what the assessment decided, so the routing publishes
it without re-deriving anything: the park to post, plus the response or the
dirty paths that park's comment quotes.
"""
from __future__ import annotations

from dataclasses import dataclass

from github.Issue import Issue

from orchestrator import config
from orchestrator.agents import AgentResult
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState


@dataclass(frozen=True)
class _DiscussionRun:
    """The stable inputs one discussion-stage tick is driven by."""

    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState

    @classmethod
    def start(
        cls, gh: GitHubClient, spec: config.RepoSpec, issue: Issue,
    ) -> _DiscussionRun:
        return cls(gh=gh, spec=spec, issue=issue, state=gh.read_pinned_state(issue))


@dataclass(frozen=True)
class _DiscussionSession:
    """The agent identity one discussion round runs and is recorded under."""

    agent_spec: str
    backend: str
    extra_args: tuple[str, ...]
    session_id: str | None


@dataclass(frozen=True)
class _DiscussionRound:
    """One finished agent round and the checkout it started from."""

    agent_result: AgentResult
    head_before: str


@dataclass(frozen=True)
class _DiscussionPrompt:
    """What one round is asked, and the replies that asking has consumed."""

    text: str
    consumed: tuple


@dataclass(frozen=True)
class _DiscussionOutcome:
    """The park a finished run earned, and what its comment quotes."""

    park_reason: str | None
    response: str = ""
    dirty_files: tuple[str, ...] = ()
