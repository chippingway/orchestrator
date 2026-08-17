# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One `discussion` tick, in the order its questions have to be asked.

Whose turn it is comes first, and a park THIS stage wrote is what settles it:
the round already posted is on the thread waiting for the humans to answer it
by number, so the tick has nothing to OPEN. What it has instead is a reply to
look for, and only a trusted comment past the consumed watermark makes it this
stage's turn again -- an untrusted one may neither steer the agent nor be
recorded as read, and no comment at all leaves the durable state exactly as the
park left it. A park any other stage wrote is not this stage's turn to wait on
-- pinned state outlives a relabel, so an issue an operator moves here from a
parked stage arrives awaiting a reply nobody will send it here, and reading
`awaiting_human` alone would leave it inert for good.

What the last round left comes next, and on an unparked issue it is asked in
two halves. A commit found against the anchor a round opened with belongs to a
round that never reached a disposition -- withheld by a mid-run pause, or cut
short -- and it is named now because the alternative is the next round adopting
it as its own baseline. Then uncommitted work, because preparing the checkout
is destructive: `_ensure_worktree` would recreate the tree over changes that
are the only record of what an unfinished run was doing.

A parked issue with a reply asks both of those too, and answers them
differently: it holds silently instead of parking. The park that left the tree
in that state already carries the paths and the reset command, so a second copy
of that message on every reply would bury the one an operator has to act on --
and the reply stays unconsumed, so it is still waiting the tick after they
reset.

Everything else is the round and its disposition, in that order and nothing
after it. This stage never reaches a developer or a reviewer and never opens a
PR: the design is not settled until a human says so on the thread, so what a
tick can produce is an analysis to reply to and a park to reply into, however
many rounds the conversation runs. The worktree the round ran in survives every
one of those exits, because the tree the discussion read is the tree the next
round and the operator both look at.
"""
from __future__ import annotations

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.workflow.stages.discussion import models as _models
from orchestrator.workflow.stages.discussion import outcomes as _outcomes
from orchestrator.workflow.stages.discussion import parks as _parks
from orchestrator.workflow.stages.discussion import run as _run
from orchestrator.workflow.stages.discussion import session as _session
from orchestrator.workflow.stages.discussion import state as _state


def _run_discussion_round(
    run: _models._DiscussionRun, replies: list | None = None,
) -> None:
    """Open one round and publish whatever it turns out to have left."""
    round_result = _run._open_discussion_round(run, replies)
    outcome = _outcomes._assess_discussion_outcome(run, round_result)
    if outcome.park_reason is not None:
        _outcomes._route_discussion_outcome(run, round_result, outcome)


def _resume_parked_discussion(run: _models._DiscussionRun) -> None:
    """Answer the humans' reply to the parked round, or leave it parked.

    A tick nobody has answered is a no-op in the strict sense -- nothing
    spawned, nothing posted, no durable write -- so a parked discussion costs
    one comment read a tick and keeps waiting exactly as its park left it.
    """
    new_replies = _session._new_trusted_replies(run)
    if not new_replies:
        return
    if _hold_resume_for_repair(run):
        return
    _run_discussion_round(run, new_replies)


def _hold_resume_for_repair(run: _models._DiscussionRun) -> bool:
    """True when the checkout has to be repaired before a round may open.

    Said once and then held quietly. The park written here is itself a repair
    request, so the reply after it changes nothing on the thread -- and a park
    that ALREADY carried those instructions (this issue is sitting on the
    commit or dirty-tree park that reported the violation in the first place)
    is not repeated at all. Only a tree that went wrong under a clean park owes
    the humans an explanation, and without one they would answer the frontier
    and get silence.

    The reply survives every one of those paths: no round opens, so nothing
    consumes it, and the park preserves the ceiling the last round read
    through. Resetting the tree is the whole of what an operator has to do --
    the answer they already wrote is picked up on the next tick.
    """
    already_asked = _state._repair_already_requested(run.state)
    if _run._round_anchor_moved(run):
        if not already_asked:
            _parks._park_blocked_resume(run, ())
        return True
    stranded_files = _run._stranded_dirty_files(run)
    if not stranded_files:
        return False
    if not already_asked:
        _parks._park_blocked_resume(run, stranded_files)
    return True


def _handle_discussion(
    gh: GitHubClient, spec: config.RepoSpec, issue: Issue,
) -> None:
    """Open the discussion, answer the humans in it, or wait on them."""
    discussion_run = _models._DiscussionRun.start(gh, spec, issue)
    if _state._parked_by_discussion(discussion_run.state):
        _resume_parked_discussion(discussion_run)
        return
    if _run._round_anchor_moved(discussion_run):
        _parks._park_recovered_commit(discussion_run)
        return
    stranded_files = _run._stranded_dirty_files(discussion_run)
    if stranded_files:
        _parks._park_stranded_worktree(discussion_run, stranded_files)
        return
    _run_discussion_round(discussion_run)
