# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One `discussion` tick, in the order its three questions have to be asked.

Whose turn it is comes first. A park THIS stage wrote outranks everything: the
round already posted is on the thread waiting for the humans to answer it by
number, and a second round spawned over the top of that would replace the
question they are mid-answer with a differently-worded one. A park any other
stage wrote is not this stage's turn to wait on -- pinned state outlives a
relabel, so an issue an operator moves here from a parked stage arrives
awaiting a reply nobody will send it here, and reading `awaiting_human` alone
would leave it inert for good.

What the last round left comes next, and it is asked in two halves. A commit
found against the anchor a round opened with belongs to a round that never
reached a disposition -- withheld by a mid-run pause, or cut short -- and it is
named now because the alternative is the next round adopting it as its own
baseline. Then uncommitted work, because preparing the checkout is destructive:
`_ensure_worktree` would recreate the tree over changes that are the only
record of what an unfinished run was doing.

Everything else is the opening round and its disposition, in that order and
nothing after it. This stage never reaches a developer or a reviewer and never
opens a PR: the design is not settled until a human says so on the thread, so
what a tick can produce is an analysis to reply to and a park to reply into.
The worktree the round ran in survives every one of those exits, because the
tree the discussion read is the tree the next round and the operator both look
at.
"""
from __future__ import annotations

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.workflow.stages.discussion import models as _models
from orchestrator.workflow.stages.discussion import outcomes as _outcomes
from orchestrator.workflow.stages.discussion import parks as _parks
from orchestrator.workflow.stages.discussion import run as _run
from orchestrator.workflow.stages.discussion import state as _state


def _run_discussion_round(run: _models._DiscussionRun) -> None:
    """Open one round and publish whatever it turns out to have left."""
    round_result = _run._open_discussion_round(run)
    outcome = _outcomes._assess_discussion_outcome(run, round_result)
    if outcome.park_reason is not None:
        _outcomes._route_discussion_outcome(run, round_result, outcome)


def _handle_discussion(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue,
) -> None:
    """Open the discussion, or leave a parked one to the humans in it."""
    discussion_run = _models._DiscussionRun.start(gh, spec, issue)
    if _state._parked_by_discussion(discussion_run.state):
        return
    if _run._unfinished_round_committed(discussion_run):
        _parks._park_recovered_commit(discussion_run)
        return
    stranded_files = _run._stranded_dirty_files(discussion_run)
    if stranded_files:
        _parks._park_stranded_worktree(discussion_run, stranded_files)
        return
    _run_discussion_round(discussion_run)
